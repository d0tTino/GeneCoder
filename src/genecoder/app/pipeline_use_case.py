from __future__ import annotations

"""Authoritative application orchestration entrypoint.

`RunPipelineUseCase` is the canonical public orchestration API for GeneCoder
runtime execution. Internally it delegates to `genecoder.core.run_canonical_pipeline`
via `genecoder.app.pipeline_runtime.run_pipeline`, which returns metrics derived
from the canonical runtime model (`genecoder.core.CanonicalRuntimeResult`).
"""

from dataclasses import dataclass, field
import base64
import hashlib
from importlib import metadata
import json
from pathlib import Path
from typing import Any, Mapping, cast

from genecoder.manifest import generate_manifest
from .pipeline_runtime import ProfileParameterOverrides, run_pipeline
from genecoder.results.schema import RUN_SCHEMA_VERSION, canonical_metrics_view
from genecoder.html_report import generate_html_report
from genecoder.runtime import make_run_context
from genecoder.profiles.registry import canonicalize_profile_name


@dataclass(frozen=True)
class ChannelProfile:
    name: str
    parameters: ProfileParameterOverrides = field(default_factory=dict)


@dataclass(frozen=True)
class SeedProfile:
    global_seed: int | None = None
    encode_seed: int | None = None
    simulate_seed: int | None = None
    decode_seed: int | None = None


@dataclass(frozen=True)
class BatchSweepMatrix:
    axes: Mapping[str, tuple[Any, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class ConstraintProfile:
    min_length: int | None = None
    max_length: int | None = None
    gc_min: float | None = None
    gc_max: float | None = None
    max_homopolymer: int | None = None


@dataclass(frozen=True)
class ArtifactOutputPolicy:
    metrics_path: str | None = None
    emit_manifest: bool = True
    emit_html_report: bool = False
    attestation_private_key_path: str | None = None
    attestation_signature_path: str | None = None


@dataclass(frozen=True)
class RunPipelineRequest:
    codec: str
    input_path: str
    output_path: str
    fec: str | None = None
    channel: str | None = None
    filter_mutated: bool = False
    profile: ChannelProfile | None = None
    seeds: SeedProfile | None = None
    matrix: BatchSweepMatrix | None = None
    constraints: ConstraintProfile | None = None
    artifacts: ArtifactOutputPolicy = field(default_factory=ArtifactOutputPolicy)


@dataclass(frozen=True)
class RunPipelineResponse:
    decoded: bytes
    dashboard_metrics: Mapping[str, Any]
    run_schema: Mapping[str, Any]
    fec_info: Mapping[str, Any] | None
    metrics_path: str
    manifest_path: str | None
    html_report_path: str | None


_PACKAGE_VERSION_NAMES: tuple[str, ...] = (
    "GeneCoder",
    "cryptography",
    "reedsolo",
    "PyYAML",
    "portalocker",
    "httpx",
    "jsonschema",
    "numpy",
    "pandas",
    "dnachisel",
    "chamaeleo",
    "bchlib",
    "raptorq",
)


def _normalize_for_attestation(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _normalize_for_attestation(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_normalize_for_attestation(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return value


def _canonical_attestation_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        _normalize_for_attestation(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in _PACKAGE_VERSION_NAMES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _plugin_lock_state() -> list[dict[str, Any]]:
    try:
        from genecoder.plugin_supply_chain.service import PLUGIN_LOCK
    except Exception:  # pragma: no cover - defensive import isolation
        return []
    return [dict(entry) for entry in PLUGIN_LOCK]


def _file_sha256(path: str) -> str | None:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sign_attestation(payload_bytes: bytes, private_key_path: str) -> dict[str, Any]:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

    key_bytes = Path(private_key_path).read_bytes()
    private_key = serialization.load_pem_private_key(key_bytes, password=None)
    if isinstance(private_key, rsa.RSAPrivateKey):
        signature = private_key.sign(payload_bytes, padding.PKCS1v15(), hashes.SHA256())
        algorithm = "RSASSA-PKCS1v15-SHA256"
        padding_scheme = "pkcs1"
    elif isinstance(private_key, ec.EllipticCurvePrivateKey):
        signature = private_key.sign(payload_bytes, ec.ECDSA(hashes.SHA256()))
        algorithm = "ECDSA-SHA256"
        padding_scheme = "ecdsa"
    else:  # pragma: no cover - unsupported key type
        raise ValueError("Unsupported attestation private key type")

    public_key_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return {
        "algorithm": algorithm,
        "padding_scheme": padding_scheme,
        "signature": base64.b64encode(signature).decode("ascii"),
        "public_key_sha256": hashlib.sha256(public_key_bytes).hexdigest(),
    }


def _build_attestation_payload(
    *,
    request: RunPipelineRequest,
    resolved_channel_name: str | None,
    resolved_profile_name: str | None,
    applied_channel_parameters: object,
    seed_provenance: Mapping[str, Any],
) -> dict[str, object]:
    constraints = (
        {
            "min_length": request.constraints.min_length,
            "max_length": request.constraints.max_length,
            "gc_min": request.constraints.gc_min,
            "gc_max": request.constraints.gc_max,
            "max_homopolymer": request.constraints.max_homopolymer,
        }
        if request.constraints
        else {}
    )
    payload: dict[str, object] = {
        "schema_version": "genecoder.reproducibility.attestation.v1",
        "config": {
            "codec": request.codec,
            "fec": request.fec,
            "channel": request.channel,
            "resolved_channel": resolved_channel_name,
            "filter_mutated": request.filter_mutated,
            "constraints": constraints,
            "sweep": dict(request.matrix.axes) if request.matrix else {},
            "input": {
                "basename": Path(request.input_path).name,
                "sha256": _file_sha256(request.input_path),
            },
        },
        "resolved_profiles": {
            "encoding": request.codec,
            "simulation": resolved_profile_name if resolved_profile_name else resolved_channel_name,
            "decode": request.codec,
            "channel_profile": (
                {
                    "requested_name": request.profile.name,
                    "resolved_name": resolved_profile_name or request.profile.name,
                    "parameters": dict(applied_channel_parameters) if isinstance(applied_channel_parameters, Mapping) else {},
                }
                if request.profile
                else None
            ),
        },
        "seed_provenance": dict(seed_provenance),
        "package_versions": _package_versions(),
        "plugin_lock_state": _plugin_lock_state(),
    }
    return cast(dict[str, object], _normalize_for_attestation(payload))


class RunPipelineUseCase:
    """Execute the canonical encode/simulate/decode orchestration flow."""

    def execute(self, request: RunPipelineRequest) -> RunPipelineResponse:
        run_context = make_run_context(
            global_seed=request.seeds.global_seed if request.seeds else None,
            encode_seed=request.seeds.encode_seed if request.seeds else None,
            simulate_seed=request.seeds.simulate_seed if request.seeds else None,
            decode_seed=request.seeds.decode_seed if request.seeds else None,
        )
        resolved_profile_name = (
            canonicalize_profile_name(request.profile.name) if request.profile else None
        )
        resolved_channel_name = canonicalize_profile_name(request.channel)

        decoded, metrics, fec_info = run_pipeline(
            codec=request.codec,
            fec_backend=request.fec,
            channel=resolved_channel_name,
            input_path=request.input_path,
            output_path=request.output_path,
            filter_mutated=request.filter_mutated,
            run_context=run_context,
            profile_parameter_overrides=(request.profile.parameters if request.profile else None),
        )

        sim_stage_provenance = metrics.pop("_sim_stage_provenance", [])
        sim_stage_metrics = metrics.pop("_sim_stage_metrics", [])
        runtime_metrics = metrics.pop("_runtime", {})
        applied_channel_parameters = metrics.pop("_applied_channel_parameters", dict(request.profile.parameters) if request.profile else {})

        constraint_outcomes_raw = metrics.get("constraint_outcomes")
        constraint_outcomes_payload = (
            constraint_outcomes_raw if isinstance(constraint_outcomes_raw, Mapping) else {}
        )
        constraint_by_oligo_raw = constraint_outcomes_payload.get("by_oligo")
        constraint_by_oligo = (
            constraint_by_oligo_raw if isinstance(constraint_by_oligo_raw, Mapping) else {}
        )
        constraint_stage_breakdown_raw = constraint_outcomes_payload.get("stages")
        constraint_stage_breakdown = (
            constraint_stage_breakdown_raw
            if isinstance(constraint_stage_breakdown_raw, list)
            else []
        )

        seed_provenance = run_context.seed_provenance()
        attestation_payload = _build_attestation_payload(
            request=request,
            resolved_channel_name=resolved_channel_name,
            resolved_profile_name=resolved_profile_name,
            applied_channel_parameters=applied_channel_parameters,
            seed_provenance=seed_provenance,
        )
        attestation_bytes = _canonical_attestation_bytes(attestation_payload)
        run_fingerprint = hashlib.sha256(attestation_bytes).hexdigest()
        attestation: dict[str, Any] = {
            "schema_version": "genecoder.reproducibility.attestation.v1",
            "canonicalization": "json-sort-keys-separators-comma-colon-utf8",
            "hash_algorithm": "sha256",
            "payload": attestation_payload,
            "run_fingerprint": run_fingerprint,
        }
        if request.artifacts.attestation_private_key_path:
            signature = _sign_attestation(attestation_bytes, request.artifacts.attestation_private_key_path)
            attestation["signature"] = signature
            if request.artifacts.attestation_signature_path:
                signature_path = Path(request.artifacts.attestation_signature_path)
                signature_path.parent.mkdir(parents=True, exist_ok=True)
                signature_path.write_text(json.dumps(signature, indent=2, sort_keys=True), encoding="utf-8")
                attestation["signature"]["path"] = str(signature_path)

        metrics_path = Path(request.artifacts.metrics_path or str(request.output_path) + ".json")
        run_schema: dict[str, Any] = {
            "schema_version": RUN_SCHEMA_VERSION,
            "source_format": "pipeline_use_case",
            "run_id": Path(request.output_path).stem,
            "run_fingerprint": run_fingerprint,
            "attestation": attestation,
            "profiles": {
                "encoding": request.codec,
                "simulation": resolved_profile_name if resolved_profile_name else resolved_channel_name,
                "decode": request.codec,
            },
            "seeds": {
                "global": run_context.global_seed,
                "encode": run_context.encode_seed,
                "simulate": run_context.simulate_seed,
                "decode": run_context.decode_seed,
                "provenance": seed_provenance,
            },
            "runtime": {
                "total_seconds": runtime_metrics.get("total_seconds"),
                "encode_seconds": runtime_metrics.get("encode_seconds"),
                "simulate_seconds": runtime_metrics.get("simulate_seconds"),
                "decode_seconds": runtime_metrics.get("decode_seconds"),
            },
            "stages": {
                "encode": {
                    "parameters": {"codec": request.codec, "fec": request.fec},
                    "metrics": {
                        "gc_content": metrics.get("gc_content"),
                        "gc_variance": metrics.get("gc_variance"),
                        "max_homopolymer": metrics.get("max_homopolymer"),
                    },
                },
                "simulate": {
                    "profile": resolved_profile_name if resolved_profile_name else resolved_channel_name,
                    "parameters": dict(applied_channel_parameters) if isinstance(applied_channel_parameters, Mapping) else {},
                    "provenance": sim_stage_provenance,
                    "metrics": {
                        "substitutions": metrics.get("substitutions"),
                        "insertions": metrics.get("insertions"),
                        "deletions": metrics.get("deletions"),
                        "coverage": metrics.get("coverage"),
                        "dropout_count": metrics.get("dropout_count"),
                        "dropout_fraction": metrics.get("dropout_fraction"),
                        "stage_metrics": sim_stage_metrics if isinstance(sim_stage_metrics, list) else [],
                    },
                },
                "decode": {
                    "parameters": {"codec": request.codec, "fec": request.fec},
                    "metrics": {
                        "decode_success": metrics.get("decode_success"),
                        "decode_success_rate": metrics.get("decode_success_rate"),
                        "ecc_success_rates": metrics.get("ecc_success_rates", {}),
                    },
                },
            },
            "sweep": dict(request.matrix.axes) if request.matrix else {},
            "constraints": (
                {
                    "min_length": request.constraints.min_length,
                    "max_length": request.constraints.max_length,
                    "gc_min": request.constraints.gc_min,
                    "gc_max": request.constraints.gc_max,
                    "max_homopolymer": request.constraints.max_homopolymer,
                }
                if request.constraints
                else {}
            ),
            "input_config": {
                "codec": request.codec,
                "fec": request.fec,
                "channel": resolved_channel_name,
                "channel_profile": (
                    {
                        "name": resolved_profile_name or request.profile.name,
                        "parameters": dict(applied_channel_parameters) if isinstance(applied_channel_parameters, Mapping) else {},
                    }
                    if request.profile
                    else None
                ),
            },
            "outcome": {
                "metrics": dict(metrics),
                "fec_info": dict(fec_info) if isinstance(fec_info, Mapping) else fec_info,
            },
            "constraint_outcomes": {
                "summary": metrics.get("constraint_violations"),
                "by_oligo": dict(constraint_by_oligo),
                "stages": list(constraint_stage_breakdown),
            },
            "decode_outcomes": {
                "decode_success": metrics.get("decode_success"),
                "decode_success_rate": metrics.get("decode_success_rate"),
                "ecc_success_rates": metrics.get("ecc_success_rates", {}),
            },
            "provenance": {
                "source_format": "pipeline_use_case",
                "generator": "RunPipelineUseCase",
            },
        }
        dashboard_metrics = canonical_metrics_view(run_schema)
        run_schema["dashboard_metrics"] = dashboard_metrics

        metrics_path.write_text(json.dumps(run_schema, indent=2), encoding="utf-8")

        manifest_path: str | None = None
        if request.artifacts.emit_manifest:
            manifest = generate_manifest(
                request.input_path,
                {"method": request.codec, "fec": request.fec, "channel": resolved_channel_name, "seeds": seed_provenance},
                dashboard_metrics,
            )
            manifest["run_fingerprint"] = run_fingerprint
            manifest["attestation"] = attestation
            manifest_file = metrics_path.with_suffix(".manifest.json")
            manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            manifest_path = str(manifest_file)

        html_report_path: str | None = None
        if request.artifacts.emit_html_report and manifest_path:
            report_path = metrics_path.with_suffix(".html")
            report_path.write_text(generate_html_report(manifest_path), encoding="utf-8")
            html_report_path = str(report_path)

        return RunPipelineResponse(
            decoded=decoded,
            dashboard_metrics=dashboard_metrics,
            run_schema=run_schema,
            fec_info=dict(fec_info) if isinstance(fec_info, Mapping) else None,
            metrics_path=str(metrics_path),
            manifest_path=manifest_path,
            html_report_path=html_report_path,
        )
