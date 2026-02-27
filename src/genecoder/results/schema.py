from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import IO, Any, Mapping

RUN_SCHEMA_VERSION = "1.1"
SUPPORTED_SCHEMA_VERSIONS: tuple[str, ...] = ("1.0", "1.1")
SCHEMA_DEPRECATIONS: dict[str, dict[str, str]] = {
    "1.0": {
        "deprecated_in": "1.1",
        "supported_until": "2.0",
        "notes": "Legacy metric mirroring remains available only through explicit migration commands.",
    }
}


def _as_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _coerce_success(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) > 0
    return None


def _decode_success_rate(metrics: Mapping[str, Any]) -> float | None:
    explicit = _as_float(metrics.get("decode_success_rate"))
    if explicit is not None:
        return explicit
    ecc = metrics.get("ecc_success_rates")
    if not isinstance(ecc, Mapping) or not ecc:
        return None
    values: list[float] = []
    for value in ecc.values():
        as_float = _as_float(value)
        if as_float is not None:
            values.append(as_float)
    if not values:
        return None
    return sum(values) / len(values)


def _normalize_runtime(runtime: Mapping[str, Any] | None) -> dict[str, float | None]:
    if not isinstance(runtime, Mapping):
        return {
            "total_seconds": None,
            "encode_seconds": None,
            "simulate_seconds": None,
            "decode_seconds": None,
        }
    return {
        "total_seconds": _as_float(runtime.get("total_seconds")),
        "encode_seconds": _as_float(runtime.get("encode_seconds")),
        "simulate_seconds": _as_float(runtime.get("simulate_seconds")),
        "decode_seconds": _as_float(runtime.get("decode_seconds")),
    }


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def canonical_metrics_view(run_data: Mapping[str, Any]) -> dict[str, Any]:
    """Return dashboard/report metrics derived from canonical schema fields."""

    run = migrate_run_schema(run_data)
    stages = _mapping(run.get("stages"))
    encode_metrics = _mapping(_mapping(stages.get("encode")).get("metrics"))
    simulate_metrics = _mapping(_mapping(stages.get("simulate")).get("metrics"))
    decode_metrics = _mapping(_mapping(stages.get("decode")).get("metrics"))
    outcome = _mapping(run.get("outcome"))
    embedded_metrics = _mapping(outcome.get("metrics"))

    metrics: dict[str, Any] = dict(embedded_metrics)
    metrics.update(
        {
            "gc_distribution": metrics.get("gc_distribution", []),
            "gc_content": encode_metrics.get("gc_content", metrics.get("gc_content")),
            "gc_variance": encode_metrics.get("gc_variance", outcome.get("gc_stress")),
            "max_homopolymer": encode_metrics.get(
                "max_homopolymer", outcome.get("homopolymer_stress")
            ),
            "homopolymer_runs": metrics.get("homopolymer_runs", []),
            "ecc_success_rates": decode_metrics.get(
                "ecc_success_rates", metrics.get("ecc_success_rates", {})
            ),
            "decode_success_rate": decode_metrics.get(
                "decode_success_rate", outcome.get("decode_success_rate")
            ),
            "decode_success": decode_metrics.get(
                "decode_success", outcome.get("decode_success")
            ),
            "substitutions": simulate_metrics.get("substitutions", metrics.get("substitutions")),
            "insertions": simulate_metrics.get("insertions", metrics.get("insertions")),
            "deletions": simulate_metrics.get("deletions", metrics.get("deletions")),
            "substitutions_histogram": metrics.get("substitutions_histogram", []),
            "insertions_histogram": metrics.get("insertions_histogram", []),
            "deletions_histogram": metrics.get("deletions_histogram", []),
            "coverage": simulate_metrics.get("coverage", metrics.get("coverage")),
            "coverage_distribution": metrics.get("coverage_distribution", []),
            "constraint_violations": metrics.get("constraint_violations"),
            "oligo_metrics": metrics.get("oligo_metrics", {}),
            "dropout_count": simulate_metrics.get("dropout_count", metrics.get("dropout_count")),
            "dropout_fraction": simulate_metrics.get(
                "dropout_fraction", outcome.get("dropout_rate")
            ),
            "dropout_rate": outcome.get("dropout_rate"),
            "ber": outcome.get("ber"),
            "throughput": outcome.get("throughput"),
        }
    )
    return metrics


def canonical_comparison_metrics(run_data: Mapping[str, Any]) -> dict[str, float | bool | None]:
    run = migrate_run_schema(run_data)
    outcome = _mapping(run.get("outcome"))
    decode = _mapping(_mapping(_mapping(run.get("stages")).get("decode")).get("metrics"))
    return {
        "ber": _as_float(outcome.get("ber")),
        "throughput": _as_float(outcome.get("throughput")),
        "dropout_rate": _as_float(outcome.get("dropout_rate")),
        "gc_stress": _as_float(outcome.get("gc_stress")),
        "homopolymer_stress": _as_float(outcome.get("homopolymer_stress")),
        "decode_success": _coerce_success(
            decode.get("decode_success")
            if decode.get("decode_success") is not None
            else outcome.get("decode_success")
        ),
    }


def translate_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    metrics = manifest.get("metrics") if isinstance(manifest.get("metrics"), Mapping) else manifest
    metrics = dict(metrics) if isinstance(metrics, Mapping) else {}
    encoding_params = manifest.get("encoding_parameters")
    if not isinstance(encoding_params, Mapping):
        encoding_params = {}
    channel = metrics.get("channel")
    if not isinstance(channel, Mapping):
        channel = {}

    decode_success_rate = _decode_success_rate(metrics)
    decode_success = _coerce_success(metrics.get("decode_success"))
    if decode_success is None and decode_success_rate is not None:
        decode_success = decode_success_rate >= 1.0

    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "source_format": "manifest",
        "run_id": str(manifest.get("file") or manifest.get("run_id") or "run"),
        "profiles": {
            "encoding": encoding_params.get("method"),
            "simulation": channel.get("name"),
            "decode": metrics.get("decoder") or metrics.get("decode_method"),
        },
        "seeds": {
            "global": metrics.get("seed"),
            "encode": metrics.get("encode_seed"),
            "simulate": metrics.get("simulate_seed") or metrics.get("sequence_batch", {}).get("seed") if isinstance(metrics.get("sequence_batch"), Mapping) else None,
            "decode": metrics.get("decode_seed"),
            "provenance": (
                metrics.get("seed_provenance")
                or encoding_params.get("seeds")
                or encoding_params.get("seed_provenance")
            ),
        },
        "runtime": _normalize_runtime(metrics.get("runtime") if isinstance(metrics.get("runtime"), Mapping) else None),
        "stages": {
            "encode": {
                "parameters": dict(encoding_params),
                "metrics": {
                    "original_size": metrics.get("original_size"),
                    "dna_length": metrics.get("dna_length"),
                    "bits_per_nt": metrics.get("bits_per_nt"),
                    "gc_content": metrics.get("gc_content"),
                    "gc_variance": metrics.get("gc_variance"),
                    "max_homopolymer": metrics.get("max_homopolymer"),
                },
            },
            "simulate": {
                "profile": channel.get("name"),
                "metrics": {
                    "dropout_count": metrics.get("dropout_count") or (channel.get("dropout", {}).get("count") if isinstance(channel.get("dropout"), Mapping) else None),
                    "dropout_fraction": metrics.get("dropout_fraction") or (channel.get("dropout", {}).get("fraction") if isinstance(channel.get("dropout"), Mapping) else None),
                    "coverage": metrics.get("coverage"),
                    "substitutions": metrics.get("substitutions"),
                    "insertions": metrics.get("insertions"),
                    "deletions": metrics.get("deletions"),
                },
            },
            "decode": {
                "metrics": {
                    "decode_success": decode_success,
                    "decode_success_rate": decode_success_rate,
                    "ber": metrics.get("ber"),
                    "throughput": metrics.get("throughput"),
                    "ecc_success_rates": metrics.get("ecc_success_rates"),
                }
            },
        },
        "outcome": {
            "ber": _as_float(metrics.get("ber")),
            "throughput": _as_float(metrics.get("throughput")),
            "dropout_rate": _as_float(metrics.get("dropout_fraction"))
            or _as_float(metrics.get("dropout_rate"))
            or _as_float(channel.get("dropout", {}).get("fraction") if isinstance(channel.get("dropout"), Mapping) else None),
            "gc_stress": _as_float(metrics.get("gc_variance")),
            "homopolymer_stress": _as_float(metrics.get("max_homopolymer")),
            "decode_success": decode_success,
            "decode_success_rate": decode_success_rate,
            "metrics": dict(metrics),
        },
    }


def translate_bundle_metrics(bundle_metrics: Mapping[str, Any], *, run_id: str = "bundle") -> dict[str, Any]:
    data = dict(bundle_metrics)
    throughput = _as_float(data.get("throughput"))
    if throughput is None:
        total_nt = _as_float(data.get("total_dna_length")) or 0.0
        total_cov = _as_float(data.get("total_coverage")) or 0.0
        throughput = total_nt if total_cov <= 0 else total_nt / total_cov

    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "source_format": "bundle_metrics",
        "run_id": run_id,
        "profiles": {"encoding": None, "simulation": None, "decode": None},
        "seeds": {"global": None, "encode": None, "simulate": None, "decode": None},
        "runtime": _normalize_runtime(None),
        "stages": {
            "encode": {"metrics": {"files": data.get("files"), "total_original_size": data.get("total_original_size"), "total_dna_length": data.get("total_dna_length"), "avg_bits_per_nt": data.get("avg_bits_per_nt")}},
            "simulate": {"metrics": {"total_substitutions": data.get("total_substitutions"), "total_insertions": data.get("total_insertions"), "total_deletions": data.get("total_deletions"), "total_coverage": data.get("total_coverage"), "total_constraint_violations": data.get("total_constraint_violations")}},
            "decode": {"metrics": {}},
        },
        "outcome": {
            "ber": _as_float(data.get("ber")),
            "throughput": throughput,
            "dropout_rate": _as_float(data.get("dropout_rate")),
            "gc_stress": _as_float(data.get("gc_stress")),
            "homopolymer_stress": _as_float(data.get("homopolymer_stress")),
            "decode_success": _coerce_success(data.get("decode_success")),
            "decode_success_rate": _as_float(data.get("decode_success_rate")),
            "metrics": data,
        },
    }


def translate_decode_summary(summary: Mapping[str, Any], *, run_id: str = "decode") -> dict[str, Any]:
    data = dict(summary)
    decode_success_rate = _as_float(data.get("decode_success_rate"))
    decode_success = _coerce_success(data.get("decode_success"))
    if decode_success is None and decode_success_rate is not None:
        decode_success = decode_success_rate >= 1.0

    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "source_format": "decode_summary",
        "run_id": run_id,
        "profiles": {
            "encoding": data.get("encoding_profile"),
            "simulation": data.get("simulation_profile"),
            "decode": data.get("decode_profile") or data.get("decoder"),
        },
        "seeds": {
            "global": data.get("seed"),
            "encode": data.get("encode_seed"),
            "simulate": data.get("simulate_seed"),
            "decode": data.get("decode_seed"),
        },
        "runtime": _normalize_runtime(data.get("runtime") if isinstance(data.get("runtime"), Mapping) else None),
        "stages": {
            "encode": {"metrics": {}},
            "simulate": {"metrics": {"dropout_count": data.get("dropout_count"), "dropout_fraction": data.get("dropout_fraction")}},
            "decode": {"metrics": dict(data)},
        },
        "outcome": {
            "ber": _as_float(data.get("ber")),
            "throughput": _as_float(data.get("throughput")),
            "dropout_rate": _as_float(data.get("dropout_fraction")) or _as_float(data.get("dropout_rate")),
            "gc_stress": _as_float(data.get("gc_stress")) or _as_float(data.get("gc_variance")),
            "homopolymer_stress": _as_float(data.get("homopolymer_stress")) or _as_float(data.get("max_homopolymer")),
            "decode_success": decode_success,
            "decode_success_rate": decode_success_rate,
            "metrics": dict(data),
        },
    }


def migrate_run_schema(run_data: Mapping[str, Any], target_version: str = RUN_SCHEMA_VERSION) -> dict[str, Any]:
    data = copy.deepcopy(dict(run_data))
    current = data.get("schema_version")
    if current == target_version:
        return data

    if current in {None, "", 1, "1", "1.0", "1.1"}:
        # v1.x migration is mostly shape normalization.
        if "outcome" not in data or not isinstance(data.get("outcome"), Mapping):
            data = translate_manifest(data)
        data["schema_version"] = RUN_SCHEMA_VERSION
        data.setdefault("schema_support", dict(SCHEMA_DEPRECATIONS))
        return data

    # Unknown future version: keep payload but mark requested target.
    data["schema_version"] = target_version
    return data


def load_run_schema(src: str | Path | IO[str] | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(src, Mapping):
        raw: dict[str, Any] = dict(src)
    elif hasattr(src, "read"):
        raw = json.load(src)
    else:
        with open(src, "r", encoding="utf-8") as fh:
            raw = json.load(fh)

    if not isinstance(raw, Mapping):
        return translate_manifest({})
    data = dict(raw)

    if data.get("schema_version"):
        if isinstance(data.get("outcome"), Mapping):
            return migrate_run_schema(data)
        if isinstance(data.get("metrics"), Mapping) or "encoding_parameters" in data:
            return migrate_run_schema(translate_manifest(data))
        return migrate_run_schema(data)
    if isinstance(data.get("metrics"), Mapping) or "encoding_parameters" in data:
        return migrate_run_schema(translate_manifest(data))
    if "total_original_size" in data and "files" in data:
        return migrate_run_schema(translate_bundle_metrics(data))
    if any(key in data for key in ("gc_distribution", "gc_content", "max_homopolymer", "constraint_violations", "oligo_metrics")):
        return migrate_run_schema(translate_manifest({"file": data.get("run_id") or "run", "encoding_parameters": {"method": data.get("method") or "unknown"}, "metrics": data}))
    return migrate_run_schema(translate_decode_summary(data))


def canonical_to_legacy_metrics(run_data: Mapping[str, Any]) -> dict[str, Any]:
    run = migrate_run_schema(run_data)
    outcome = run.get("outcome") if isinstance(run.get("outcome"), Mapping) else {}
    embedded_metrics = outcome.get("metrics") if isinstance(outcome, Mapping) and isinstance(outcome.get("metrics"), Mapping) else {}
    metrics: dict[str, Any] = dict(embedded_metrics)

    if "decode_success_rate" not in metrics and isinstance(outcome, Mapping) and outcome.get("decode_success_rate") is not None:
        metrics["decode_success_rate"] = outcome.get("decode_success_rate")
    if "throughput" not in metrics and isinstance(outcome, Mapping) and outcome.get("throughput") is not None:
        metrics["throughput"] = outcome.get("throughput")
    if "ber" not in metrics and isinstance(outcome, Mapping) and outcome.get("ber") is not None:
        metrics["ber"] = outcome.get("ber")
    if "dropout_fraction" not in metrics and isinstance(outcome, Mapping) and outcome.get("dropout_rate") is not None:
        metrics["dropout_fraction"] = outcome.get("dropout_rate")
    if "gc_variance" not in metrics and isinstance(outcome, Mapping) and outcome.get("gc_stress") is not None:
        metrics["gc_variance"] = outcome.get("gc_stress")
    if "max_homopolymer" not in metrics and isinstance(outcome, Mapping) and outcome.get("homopolymer_stress") is not None:
        metrics["max_homopolymer"] = outcome.get("homopolymer_stress")

    return metrics


def _comparison_slice(run_data: Mapping[str, Any]) -> dict[str, float | bool | None]:
    return canonical_comparison_metrics(run_data)


def _metric_delta(base: float | None, candidate: float | None) -> dict[str, float | None]:
    if base is None or candidate is None:
        return {"base": base, "candidate": candidate, "absolute": None, "relative": None}
    absolute = candidate - base
    relative = None if base == 0 else absolute / base
    return {"base": base, "candidate": candidate, "absolute": absolute, "relative": relative}


def compare_runs(run_a: Mapping[str, Any], run_b: Mapping[str, Any], *other_runs: Mapping[str, Any]) -> dict[str, Any]:
    baseline = migrate_run_schema(run_a)
    candidates = [migrate_run_schema(run_b)] + [migrate_run_schema(item) for item in other_runs]

    baseline_metrics = _comparison_slice(baseline)
    comparisons: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_metrics = _comparison_slice(candidate)
        comparisons.append(
            {
                "run_id": candidate.get("run_id"),
                "metrics": {
                    "ber": _metric_delta(baseline_metrics["ber"], candidate_metrics["ber"]),
                    "throughput": _metric_delta(baseline_metrics["throughput"], candidate_metrics["throughput"]),
                    "dropout_rate": _metric_delta(baseline_metrics["dropout_rate"], candidate_metrics["dropout_rate"]),
                    "gc_stress": _metric_delta(baseline_metrics["gc_stress"], candidate_metrics["gc_stress"]),
                    "homopolymer_stress": _metric_delta(baseline_metrics["homopolymer_stress"], candidate_metrics["homopolymer_stress"]),
                    "decode_success": {
                        "base": baseline_metrics["decode_success"],
                        "candidate": candidate_metrics["decode_success"],
                        "changed": baseline_metrics["decode_success"] != candidate_metrics["decode_success"],
                    },
                },
            }
        )

    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "baseline_run_id": baseline.get("run_id"),
        "comparisons": comparisons,
    }
