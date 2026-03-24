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

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_ARTIFACT_PATH = ROOT / "artifacts" / "acceptance" / "deterministic-reproducibility-runtime.json"


def _emit_acceptance_artifact(payload: dict) -> None:
    ACCEPTANCE_ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACCEPTANCE_ARTIFACT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _run_pipeline(use_case: RunPipelineUseCase, *, input_path: Path, output_path: Path, metrics_path: Path) -> tuple[bytes, dict]:
    request = RunPipelineRequest(
        codec="reverse",
        input_path=str(input_path),
        output_path=str(output_path),
        channel="simple",
        profile=ChannelProfile(
            name="simple",
            parameters={
                "substitution_prob": 0.0,
                "insertion_prob": 0.0,
                "deletion_prob": 0.0,
                "dropout_prob": 0.0,
            },
        ),
        seeds=SeedProfile(global_seed=2026, encode_seed=2201, simulate_seed=2202, decode_seed=2203),
        artifacts=ArtifactOutputPolicy(metrics_path=str(metrics_path), emit_manifest=False, emit_html_report=False),
    )
    response = use_case.execute(request)
    return response.decoded, dict(response.run_schema)


def test_deterministic_pipeline_run_is_byte_identical_and_preserves_seed_provenance(tmp_path: Path) -> None:
    input_path = tmp_path / "input.bin"
    input_path.write_bytes(b"acceptance-deterministic-workflow")

    use_case = RunPipelineUseCase()
    decoded_first, run_schema_first = _run_pipeline(
        use_case,
        input_path=input_path,
        output_path=tmp_path / "decoded-first.bin",
        metrics_path=tmp_path / "metrics-first.json",
    )
    decoded_second, run_schema_second = _run_pipeline(
        use_case,
        input_path=input_path,
        output_path=tmp_path / "decoded-second.bin",
        metrics_path=tmp_path / "metrics-second.json",
    )

    assert decoded_first == decoded_second
    assert run_schema_first["seeds"]["provenance"] == run_schema_second["seeds"]["provenance"]
    assert run_schema_first["stages"]["simulate"]["metrics"] == run_schema_second["stages"]["simulate"]["metrics"]

    _emit_acceptance_artifact(
        {
            "suite": "deterministic_reproducibility_governance",
            "passed": True,
            "evidence": {
                "decoded_sha256_equal": True,
                "seed_provenance_equal": True,
                "simulate_stage_metrics_equal": True,
            },
            "run_ids": [run_schema_first["run_id"], run_schema_second["run_id"]],
            "seed_provenance": run_schema_first["seeds"]["provenance"],
            "simulate_stage_metrics": run_schema_first["stages"]["simulate"]["metrics"],
        }
    )
