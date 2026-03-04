from __future__ import annotations

import warnings

import pytest

from genecoder.simulation_engine.profiles import resolve_profile
from genecoder.simulators.illumina.profiles import ILLUMINA_PROFILE_PRESETS


def test_resolve_illumina_preset_versioned_profile() -> None:
    resolved = resolve_profile("miseq", kind="illumina", presets=ILLUMINA_PROFILE_PRESETS)
    assert resolved is not None
    assert resolved.schema_version == 1
    assert resolved.kind == "illumina"


def test_raw_dict_profile_requires_explicit_compat_policy() -> None:
    with pytest.raises(ValueError, match="must be versioned"):
        resolve_profile(
            {
                "substitution_rate": 0.1,
                "insertion_rate": 0.0,
                "deletion_rate": 0.0,
                "read_length": 100,
                "coverage": 1.0,
            },
            kind="illumina",
            presets=ILLUMINA_PROFILE_PRESETS,
            policy="strict",
        )


def test_raw_dict_profile_is_deprecated_in_compat_policy() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        resolve_profile(
            {
                "substitution_rate": 0.1,
                "insertion_rate": 0.0,
                "deletion_rate": 0.0,
                "read_length": 100,
                "coverage": 1.0,
            },
            kind="illumina",
            presets=ILLUMINA_PROFILE_PRESETS,
            policy="compat",
        )
    assert any(item.category is DeprecationWarning for item in caught)
