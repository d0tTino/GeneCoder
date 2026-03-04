from __future__ import annotations

import json
from pathlib import Path

from genecoder.app.pipeline_use_case import (
    ArtifactOutputPolicy,
    ChannelProfile,
    RunPipelineRequest,
    RunPipelineUseCase,
)
from genecoder.cli.bundle import _extract_channel_profile
from genecoder.profiles.registry import resolve_named_profiles
from genecoder.sdk.api import _request_from_mapping
from genecoder.simulators.profile_resolver import resolve_named_profiles as resolve_named_profiles_wrapper


FIXTURE_PATH = Path(__file__).parent / "data" / "profile_resolution_golden.json"


def test_profile_resolution_golden_parity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "genecoder.app.pipeline_use_case.run_pipeline",
        lambda **_: (b"decoded", {"decode_success": True}, None),
    )

    use_case = RunPipelineUseCase()
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    for idx, fixture in enumerate(fixtures):
        profile_alias = fixture["input"]["profile"]
        expected = fixture["expected"]

        registry_resolved = resolve_named_profiles(profile=profile_alias)
        wrapper_resolved = resolve_named_profiles_wrapper(profile=profile_alias)
        assert registry_resolved == wrapper_resolved
        assert registry_resolved.illumina_profile == expected["illumina_profile"]
        assert registry_resolved.nanopore_profile == expected["nanopore_profile"]
        assert registry_resolved.dnarsim_profile == expected["dnarsim_profile"]

        assert _extract_channel_profile({"pipeline": {"profile": profile_alias}}) == expected["canonical_name"]

        request = _request_from_mapping(
            {
                "codec": "huffman",
                "input_path": "in.txt",
                "output_path": "out.bin",
                "profile": {"name": profile_alias, "parameters": {}},
            }
        )
        assert request.profile is not None
        assert request.profile.name == expected["canonical_name"]

        output_file = tmp_path / f"out-{idx}.bin"
        response = use_case.execute(
            RunPipelineRequest(
                codec="huffman",
                input_path="in.txt",
                output_path=str(output_file),
                profile=ChannelProfile(name=profile_alias),
                artifacts=ArtifactOutputPolicy(metrics_path=str(tmp_path / f"metrics-{idx}.json")),
            )
        )
        assert response.run_schema["profiles"]["simulation"] == expected["canonical_name"]
        assert response.run_schema["input_config"]["channel_profile"]["name"] == expected["canonical_name"]
