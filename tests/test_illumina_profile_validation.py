import pytest
import json
import yaml
from pathlib import Path

from genecoder.simulators.illumina import IlluminaChannel


def test_valid_profile_file(tmp_path: Path) -> None:
    params = {
        "substitution_rate": 0.01,
        "insertion_rate": 0.02,
        "deletion_rate": 0.03,
        "read_length": 100,
        "coverage": 2,
    }
    prof = tmp_path / "good.yml"
    prof.write_text(yaml.safe_dump(params))
    ch = IlluminaChannel(profile_path=str(prof))
    assert ch.read_length == 100
    assert ch.coverage == 2


def test_valid_profile_file_json(tmp_path: Path) -> None:
    params = {
        "substitution_rate": 0.01,
        "insertion_rate": 0.02,
        "deletion_rate": 0.03,
        "read_length": 120,
        "coverage": 3,
    }
    prof = tmp_path / "good.json"
    prof.write_text(json.dumps(params))
    ch = IlluminaChannel(profile_path=str(prof))
    assert ch.read_length == 120
    assert ch.coverage == 3


@pytest.mark.parametrize(
    "bad_params, msg",
    [
        (
            {
                "substitution_rate": 0.01,
                "insertion_rate": 0.02,
                "deletion_rate": 0.03,
                "read_length": 100,
            },
            "missing required key\(s\): coverage",
        ),
        (
            {
                "substitution_rate": -0.1,
                "insertion_rate": 0.02,
                "deletion_rate": 0.03,
                "read_length": 100,
                "coverage": 2,
            },
            "substitution_rate must be between 0 and 1",
        ),
        (
            {
                "substitution_rate": 0.01,
                "insertion_rate": 0.02,
                "deletion_rate": 0.03,
                "read_length": 0,
                "coverage": 2,
            },
            "read_length must be positive",
        ),
        (
            {
                "substitution_rate": 0.01,
                "insertion_rate": 0.02,
                "deletion_rate": 0.03,
                "read_length": 100,
                "coverage": 0,
            },
            "coverage must be positive",
        ),
    ],
)
def test_invalid_profile_file(tmp_path: Path, bad_params: dict, msg: str) -> None:
    prof = tmp_path / "bad.yml"
    prof.write_text(yaml.safe_dump(bad_params))
    with pytest.raises(ValueError, match=msg):
        IlluminaChannel(profile_path=str(prof))


def test_invalid_direct_params() -> None:
    with pytest.raises(ValueError):
        IlluminaChannel(substitution_rate=2.0)
