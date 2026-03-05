from __future__ import annotations

from pathlib import Path

from genecoder.app.pipeline_use_case import ArtifactOutputPolicy, ChannelProfile, RunPipelineRequest, RunPipelineUseCase
from genecoder.channel_config import ChannelConfig
from genecoder.simulators.illumina import IlluminaChannel
from genecoder.simulators.nanopore import NanoporeChannel
from genecoder.simulators.pipeline import ChannelPipeline


def test_use_case_persists_applied_profile_parameters_and_provenance(
    monkeypatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def _fake_runtime(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return (
            b"decoded",
            {
                "decode_success": True,
                "_applied_channel_parameters": {"substitution_rate": 0.0},
                "_sim_stage_provenance": [{"stage_name": "sequencing", "parameters": {"substitution_rate": 0.0}}],
            },
            None,
        )

    monkeypatch.setattr("genecoder.app.pipeline_use_case.run_pipeline", _fake_runtime)

    output_file = tmp_path / "out.bin"
    response = RunPipelineUseCase().execute(
        RunPipelineRequest(
            codec="huffman",
            input_path="in.txt",
            output_path=str(output_file),
            profile=ChannelProfile(name="miseq", parameters={"substitution_rate": 0.0}),
            artifacts=ArtifactOutputPolicy(metrics_path=str(tmp_path / "metrics.json")),
        )
    )

    assert captured["profile_parameter_overrides"] == {"substitution_rate": 0.0}
    assert response.run_schema["input_config"]["channel_profile"]["parameters"] == {"substitution_rate": 0.0}
    assert response.run_schema["stages"]["simulate"]["provenance"] == [
        {"stage_name": "sequencing", "parameters": {"substitution_rate": 0.0}}
    ]


def test_channel_config_profile_parameter_translation_for_illumina_and_nanopore() -> None:
    illumina_pipeline = ChannelPipeline([IlluminaChannel(profile="miseq")])
    illumina_resolved = illumina_pipeline._resolve_channels(
        ChannelConfig(
            illumina_profile="miseq",
            profile_parameters={"substitution_rate": 0.0},
            illumina_parameters={"coverage": 1.0},
        )
    )
    illumina_channel = illumina_resolved[0]
    assert isinstance(illumina_channel, IlluminaChannel)
    assert illumina_channel.substitution_rate == 0.0
    assert illumina_channel.coverage == 1.0

    nanopore_pipeline = ChannelPipeline([NanoporeChannel(profile="minion")])
    nanopore_resolved = nanopore_pipeline._resolve_channels(
        ChannelConfig(
            nanopore_profile="minion",
            profile_parameters={"deletion_rate": 0.0},
            nanopore_parameters={"coverage": 2.0},
        )
    )
    nanopore_channel = nanopore_resolved[0]
    assert isinstance(nanopore_channel, NanoporeChannel)
    assert nanopore_channel.deletion_rate == 0.0
    assert nanopore_channel.coverage == 2.0
