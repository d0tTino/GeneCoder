from __future__ import annotations

import json
from pathlib import Path

from genecoder.app.pipeline_use_case import (
    ArtifactOutputPolicy,
    ChannelProfile,
    RunPipelineRequest,
    RunPipelineUseCase,
    SeedProfile,
)


FAKE_METRICS = {
    "gc_content": 0.5,
    "gc_variance": 0.0,
    "max_homopolymer": 2,
    "substitutions": 0,
    "insertions": 0,
    "deletions": 0,
    "coverage": 1,
    "dropout_count": 0,
    "dropout_fraction": 0.0,
    "decode_success": True,
    "decode_success_rate": 1.0,
    "ecc_success_rates": {},
    "constraint_violations": 0,
    "constraint_outcomes": {"by_oligo": {}, "stages": []},
    "_runtime": {
        "total_seconds": 0.1,
        "encode_seconds": 0.01,
        "simulate_seconds": 0.02,
        "decode_seconds": 0.03,
    },
    "_sim_stage_provenance": [{"stage": "simulate", "profile": "simple"}],
    "_sim_stage_metrics": [{"stage": "simulate", "coverage": 1}],
    "_applied_channel_parameters": {"substitution_prob": 0.0},
}


def _fake_runtime(**kwargs: object):
    metrics = dict(FAKE_METRICS)
    metrics["_applied_channel_parameters"] = dict(kwargs.get("profile_parameter_overrides") or {})
    return b"attested", metrics, None


def _request(tmp_path: Path, *, metrics_name: str, output_name: str, substitution_prob: float = 0.0) -> RunPipelineRequest:
    source = tmp_path / "input.bin"
    source.write_bytes(b"same reproducibility input")
    return RunPipelineRequest(
        codec="reverse",
        input_path=str(source),
        output_path=str(tmp_path / output_name),
        channel="simple",
        profile=ChannelProfile(name="simple", parameters={"substitution_prob": substitution_prob}),
        seeds=SeedProfile(global_seed=123, encode_seed=124, simulate_seed=125, decode_seed=126),
        artifacts=ArtifactOutputPolicy(metrics_path=str(tmp_path / metrics_name), emit_manifest=True),
    )


def test_identical_inputs_produce_same_reproducibility_fingerprint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("genecoder.app.pipeline_use_case.run_pipeline", _fake_runtime)

    first = RunPipelineUseCase().execute(_request(tmp_path, metrics_name="first.json", output_name="first.out"))
    second = RunPipelineUseCase().execute(_request(tmp_path, metrics_name="second.json", output_name="second.out"))

    assert first.run_schema["run_fingerprint"] == second.run_schema["run_fingerprint"]
    assert first.run_schema["attestation"]["payload"] == second.run_schema["attestation"]["payload"]

    manifest = json.loads(Path(first.manifest_path or "").read_text(encoding="utf-8"))
    assert manifest["run_fingerprint"] == first.run_schema["run_fingerprint"]
    assert manifest["attestation"]["payload"]["seed_provenance"] == first.run_schema["seeds"]["provenance"]


def test_config_drift_changes_reproducibility_fingerprint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("genecoder.app.pipeline_use_case.run_pipeline", _fake_runtime)

    baseline = RunPipelineUseCase().execute(_request(tmp_path, metrics_name="baseline.json", output_name="baseline.out"))
    drifted = RunPipelineUseCase().execute(
        _request(
            tmp_path,
            metrics_name="drifted.json",
            output_name="drifted.out",
            substitution_prob=0.01,
        )
    )

    assert baseline.run_schema["run_fingerprint"] != drifted.run_schema["run_fingerprint"]
    assert baseline.run_schema["attestation"]["payload"]["resolved_profiles"]["channel_profile"]["parameters"] != drifted.run_schema["attestation"]["payload"]["resolved_profiles"]["channel_profile"]["parameters"]


def test_attestation_signature_metadata_is_embedded_and_written(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("genecoder.app.pipeline_use_case.run_pipeline", _fake_runtime)

    def _fake_sign(payload_bytes: bytes, private_key_path: str) -> dict[str, str]:
        assert payload_bytes
        assert private_key_path == str(tmp_path / "private.pem")
        return {
            "algorithm": "test-sha256",
            "padding_scheme": "pkcs1",
            "signature": "c2ln",
            "public_key_sha256": "0" * 64,
        }

    monkeypatch.setattr("genecoder.app.pipeline_use_case._sign_attestation", _fake_sign)
    request = _request(tmp_path, metrics_name="signed.json", output_name="signed.out")
    request = RunPipelineRequest(
        codec=request.codec,
        input_path=request.input_path,
        output_path=request.output_path,
        channel=request.channel,
        profile=request.profile,
        seeds=request.seeds,
        artifacts=ArtifactOutputPolicy(
            metrics_path=request.artifacts.metrics_path,
            emit_manifest=True,
            attestation_private_key_path=str(tmp_path / "private.pem"),
            attestation_signature_path=str(tmp_path / "nested" / "attestation.sig.json"),
        ),
    )

    response = RunPipelineUseCase().execute(request)

    signature = response.run_schema["attestation"]["signature"]
    assert signature["signature"] == "c2ln"
    assert signature["path"] == str(tmp_path / "nested" / "attestation.sig.json")
    detached = json.loads((tmp_path / "nested" / "attestation.sig.json").read_text(encoding="utf-8"))
    assert detached["public_key_sha256"] == "0" * 64
    manifest = json.loads(Path(response.manifest_path or "").read_text(encoding="utf-8"))
    assert manifest["attestation"]["signature"] == signature
