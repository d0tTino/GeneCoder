from __future__ import annotations

from pathlib import Path

from genecoder.app import (
    ArtifactOutputPolicy,
    ChannelProfile,
    ConstraintProfile,
    RunPipelineRequest,
    RunPipelineUseCase,
    SeedProfile,
)
from genecoder.sdk import ExperimentRequest, run_experiment


FAKE_METRICS = {
    "gc_content": 0.52,
    "gc_variance": 0.01,
    "max_homopolymer": 2,
    "substitutions": 1,
    "insertions": 0,
    "deletions": 0,
    "coverage": 6,
    "dropout_count": 0,
    "dropout_fraction": 0.0,
    "decode_success": True,
    "decode_success_rate": 1.0,
    "ecc_success_rates": {"parity": 1.0},
    "constraint_violations": 0,
    "constraint_outcomes": {"by_oligo": {"oligo-1": []}, "stages": []},
    "_runtime": {
        "total_seconds": 1.2,
        "encode_seconds": 0.2,
        "simulate_seconds": 0.4,
        "decode_seconds": 0.6,
    },
    "_sim_stage_provenance": [{"stage": "simulate", "profile": "illumina"}],
    "_sim_stage_metrics": [{"stage": "simulate", "coverage": 6}],
    "_applied_channel_parameters": {"substitution_rate": 0.01},
}


def _build_app_request(tmp_path: Path) -> RunPipelineRequest:
    source = tmp_path / "input.bin"
    source.write_bytes(b"canonical-parity")
    return RunPipelineRequest(
        codec="reverse",
        input_path=str(source),
        output_path=str(tmp_path / "decoded.bin"),
        channel="illumina",
        profile=ChannelProfile(name="illumina", parameters={"substitution_rate": 0.01}),
        seeds=SeedProfile(global_seed=7, encode_seed=8, simulate_seed=9, decode_seed=10),
        constraints=ConstraintProfile(gc_min=0.4, gc_max=0.6, max_homopolymer=3),
        artifacts=ArtifactOutputPolicy(
            metrics_path=str(tmp_path / "run.metrics.json"),
            emit_manifest=True,
            emit_html_report=False,
        ),
    )


def _fake_runtime(**_: object):
    return b"canonical-parity", dict(FAKE_METRICS), {"backend": "stub"}


def test_app_and_sdk_requests_share_supported_workflow_surface(tmp_path: Path) -> None:
    app_request = _build_app_request(tmp_path)
    sdk_request = ExperimentRequest(
        codec=app_request.codec,
        input_path=app_request.input_path,
        output_path=app_request.output_path,
        channel=app_request.channel,
        profile=app_request.profile,
        seeds=app_request.seeds,
        matrix=app_request.matrix,
        constraints=app_request.constraints,
        artifacts=app_request.artifacts,
    )

    assert sdk_request.codec == app_request.codec
    assert sdk_request.profile == app_request.profile
    assert sdk_request.seeds == app_request.seeds
    assert sdk_request.constraints == app_request.constraints
    assert sdk_request.artifacts == app_request.artifacts


def test_app_and_sdk_runtime_results_are_parity_aligned(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("genecoder.app.pipeline_use_case.run_pipeline", _fake_runtime)

    app_request = _build_app_request(tmp_path)
    app_response = RunPipelineUseCase().execute(app_request)

    sdk_request = ExperimentRequest(
        codec=app_request.codec,
        input_path=app_request.input_path,
        output_path=app_request.output_path,
        channel=app_request.channel,
        profile=app_request.profile,
        seeds=app_request.seeds,
        matrix=app_request.matrix,
        constraints=app_request.constraints,
        artifacts=app_request.artifacts,
    )
    sdk_result = run_experiment(sdk_request)

    assert sdk_result.decoded == app_response.decoded
    assert sdk_result.dashboard_metrics == app_response.dashboard_metrics
    assert sdk_result.canonical_run == app_response.run_schema
    assert sdk_result.artifact_paths["metrics"] == app_response.metrics_path
    assert sdk_result.artifact_paths["manifest"] == app_response.manifest_path
    assert sdk_result.artifact_paths["html_report"] == app_response.html_report_path
    assert sdk_result.fec_info == app_response.fec_info


def test_sdk_yaml_and_dataclass_paths_match_app_contract(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("genecoder.app.pipeline_use_case.run_pipeline", _fake_runtime)
    app_request = _build_app_request(tmp_path)

    yaml_path = tmp_path / "request.yaml"
    yaml_path.write_text(
        """
codec: reverse
input_path: {input_path}
output_path: {output_path}
channel: illumina
profile:
  name: illumina
  parameters:
    substitution_rate: 0.01
seeds:
  global_seed: 7
  encode_seed: 8
  simulate_seed: 9
  decode_seed: 10
constraints:
  gc_min: 0.4
  gc_max: 0.6
  max_homopolymer: 3
artifacts:
  metrics_path: {metrics_path}
  emit_manifest: true
  emit_html_report: false
""".format(
            input_path=app_request.input_path,
            output_path=app_request.output_path,
            metrics_path=app_request.artifacts.metrics_path,
        ),
        encoding="utf-8",
    )

    app_response = RunPipelineUseCase().execute(app_request)
    sdk_result = run_experiment(yaml_path)

    assert sdk_result.canonical_run == app_response.run_schema
    assert sdk_result.dashboard_metrics == app_response.dashboard_metrics
