from __future__ import annotations

from genecoder.cli.bundle import _extract_channel_profile
from genecoder.sdk.api import _request_from_mapping
from genecoder.simulators.profile_resolver import resolve_named_profiles


def test_profile_resolution_contract_consistent_across_cli_bundle_sdk() -> None:
    resolved = resolve_named_profiles(profile="nova", illumina_profile=None, nanopore_profile=None, dnarsim_profile=None)
    assert resolved.illumina_profile == "novaseq"

    bundle_profile = _extract_channel_profile({"pipeline": {"profile": "nova"}})
    assert bundle_profile == "novaseq"

    request = _request_from_mapping(
        {
            "codec": "huffman",
            "input_path": "in.txt",
            "output_path": "out.bin",
            "profile": {"name": "nova", "parameters": {}},
            "seeds": {"global_seed": 42},
        }
    )
    assert request.profile is not None
    assert request.profile.name == "novaseq"
    assert request.seeds is not None
    assert request.seeds.global_seed == 42
