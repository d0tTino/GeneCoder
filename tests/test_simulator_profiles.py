from pathlib import Path

import yaml

from genecoder.simulators.illumina import IlluminaChannel, ILLUMINA_PROFILES
from genecoder.simulators.nanopore import NanoporeChannel, NANOPORE_PROFILES


def test_illumina_profiles() -> None:
    for name, params in ILLUMINA_PROFILES.items():
        ch = IlluminaChannel(**params)
        for key, value in params.items():
            assert getattr(ch, key) == value


def test_nanopore_profiles() -> None:
    for name, params in NANOPORE_PROFILES.items():
        ch = NanoporeChannel(**params)
        for key, value in params.items():
            assert getattr(ch, key) == value


def test_illumina_profile_file(tmp_path: Path) -> None:
    params = {
        "substitution_rate": 0.01,
        "insertion_rate": 0.002,
        "deletion_rate": 0.003,
        "coverage": 2,
        "read_length": 100,
    }
    prof = tmp_path / "illumina.yml"
    prof.write_text(yaml.safe_dump(params))
    ch = IlluminaChannel(profile_path=str(prof))
    assert ch.substitution_rate == params["substitution_rate"]
    assert ch.insertion_rate == params["insertion_rate"]
    assert ch.deletion_rate == params["deletion_rate"]
    assert ch.coverage == params["coverage"]
    assert ch.read_length == params["read_length"]


def test_nanopore_profile_file(tmp_path: Path) -> None:
    params = {
        "error_rate": 0.15,
        "substitution_rate": 0.02,
        "insertion_rate": 0.03,
        "deletion_rate": 0.04,
        "coverage": 3,
    }
    prof = tmp_path / "nanopore.yml"
    prof.write_text(yaml.safe_dump(params))
    ch = NanoporeChannel(profile_path=str(prof))
    assert ch.error_rate == params["error_rate"]
    assert ch.substitution_rate == params["substitution_rate"]
    assert ch.insertion_rate == params["insertion_rate"]
    assert ch.deletion_rate == params["deletion_rate"]
    assert ch.coverage == params["coverage"]


def test_named_profiles() -> None:
    illumina_params = ILLUMINA_PROFILES["hiseq"]
    illumina = IlluminaChannel(profile="hiseq")
    assert illumina.substitution_rate == illumina_params["substitution_rate"]
    assert illumina.insertion_rate == illumina_params["insertion_rate"]
    nanopore_params = NANOPORE_PROFILES["minion"]
    nanopore = NanoporeChannel(profile="minion")
    assert nanopore.error_rate == nanopore_params["error_rate"]
    assert nanopore.insertion_rate == nanopore_params["insertion_rate"]


def test_profile_fallback() -> None:
    default_illumina = IlluminaChannel()
    unknown_illumina = IlluminaChannel(profile="unknown")
    assert unknown_illumina.substitution_rate == default_illumina.substitution_rate
    default_nanopore = NanoporeChannel()
    unknown_nanopore = NanoporeChannel(profile="unknown")
    assert unknown_nanopore.error_rate == default_nanopore.error_rate

