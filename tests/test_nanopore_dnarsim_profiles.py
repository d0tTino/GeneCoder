from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

import genecoder.random_utils as random_utils
import genecoder.simulators.nanopore as nanopore
import genecoder.simulators.nanopore_external as nanopore_external
from genecoder.simulators.nanopore import (
    NANOPORE_PROFILES,
    NanoporeDNArSimChannel,
)
from tests.test_cli import run_cli_command

DATA_DIR = Path(__file__).parent / "data"


def _error_counts(original: str, mutated: str) -> tuple[int, int, int]:
    length = min(len(original), len(mutated))
    subs = sum(1 for a, b in zip(original[:length], mutated[:length]) if a != b)
    ins = len(mutated) - length
    dele = len(original) - length
    return subs, ins, dele


def test_builtin_profiles_include_context_tables() -> None:
    minion = NANOPORE_PROFILES["minion"]
    assert minion["insertion_profile"][5] == pytest.approx(0.16)
    assert minion["context_insertions"]["AA"][5] == pytest.approx(0.24)
    assert minion["context_deletions"]["AA"][5] == pytest.approx(0.26)


def test_loader_falls_back_to_context_defaults(tmp_path: Path) -> None:
    base_cfg = tmp_path / "nanopore.yml"
    base_cfg.write_text(
        "minion:\n"
        "  substitution_rate: 0.019\n"
        "  insertion_rate: 0.046\n"
        "  deletion_rate: 0.065\n"
    )
    (tmp_path / "dnarsim_rates.yaml").write_text("{}\n")

    profiles, tables = nanopore._load_profiles_from_directory(tmp_path, yaml)
    assert "minion" in profiles
    fallback = nanopore._FALLBACK_PROFILE_DATA["minion"]
    assert profiles["minion"]["context_insertions"]["AA"][5] == pytest.approx(
        fallback["context_insertions"]["AA"][5]
    )
    assert tables == {}


def test_dnarsim_profiles_gain_default_coverage(tmp_path: Path) -> None:
    dnarsim_rates = tmp_path / "dnarsim_rates.yaml"
    dnarsim_rates.write_text(
        "r9:\n"
        "  substitution_rate: 0.1\n"
        "  insertion_rate: 0.01\n"
        "  deletion_rate: 0.02\n"
    )

    profiles, tables = nanopore._load_profiles_from_directory(tmp_path, yaml)

    assert profiles["r9"]["coverage"] == pytest.approx(30.0)
    assert "coverage" not in tables["r9"]


def test_parse_valid_rate_table() -> None:
    data = yaml.safe_load((DATA_DIR / "dnarsim_rates_valid.yaml").read_text())
    tbl = next(iter(data.values()))
    parsed = nanopore._parse_rate_table(tbl)
    assert parsed["substitution_rate"] == pytest.approx(0.05)
    assert parsed["insertion_rate"] == pytest.approx(0.02)
    assert parsed["deletion_rate"] == pytest.approx(0.03)
    assert parsed["context_errors"]["AA"] == pytest.approx(0.1)
    assert parsed["insertion_profile"][3] == pytest.approx(0.2)


def test_parse_invalid_rate_table() -> None:
    data = yaml.safe_load((DATA_DIR / "dnarsim_rates_invalid.yaml").read_text())
    tbl = next(iter(data.values()))
    with pytest.raises(ValueError):
        nanopore._parse_rate_table(tbl)


def test_profile_simulation_statistics(monkeypatch: pytest.MonkeyPatch) -> None:
    data = yaml.safe_load((DATA_DIR / "dnarsim_rates_valid.yaml").read_text())
    profile_name, tbl = next(iter(data.items()))
    rates = nanopore._parse_rate_table(tbl)
    rates.update(
        {
            "substitution_rate": 1.0,
            "insertion_rate": 0.0,
            "deletion_rate": 0.0,
            "context_errors": {},
            "insertion_profile": {},
            "deletion_profile": {},
            "context_insertions": {},
            "context_deletions": {},
        }
    )
    monkeypatch.setattr(nanopore, "DNARSIM_RATE_TABLES", {profile_name: rates})
    monkeypatch.setattr(nanopore, "NANOPORE_PROFILES", {profile_name: rates})
    channel = NanoporeDNArSimChannel(error_rate=0.0, profile=profile_name)

    monkeypatch.setattr(
        nanopore_external,
        "run_dnarsim_cli",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("fallback")),
    )
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    random_utils._RNG = None

    monkeypatch.setattr(
        nanopore,
        "_simulate_fallback_jit",
        staticmethod(lambda seq, rate, rng: seq),
    )

    seq = "ACGT" * 10
    mutated = channel.simulate(seq)
    subs, ins, dele = _error_counts(seq, mutated)
    assert subs == len(seq)
    assert ins == 0
    assert dele == 0


@pytest.mark.parametrize("profile", ["r9", "r10.3", "r10.4"])
def test_dnarsim_manifest_records_profile_coverage(tmp_path: Path, profile: str) -> None:
    env = os.environ.copy()
    src_path = Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    input_file = tmp_path / "input.fasta"
    input_file.write_text(">seq1\n" + "ACGT" * 8 + "\n", encoding="utf-8")
    output_file = tmp_path / "out.fasta"

    result = run_cli_command(
        [
            "channel",
            "apply",
            "--profile",
            profile,
            "--input-file",
            str(input_file),
            "--output-file",
            str(output_file),
        ],
        env=env,
    )

    assert result.returncode == 0, result.stderr

    manifest_path = output_file.with_suffix(".manifest.json")
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    coverage = manifest_data.get("coverage", {})

    expected_coverage = NANOPORE_PROFILES[profile]["coverage"]
    assert coverage.get("average") == pytest.approx(expected_coverage)
    histogram = coverage.get("histogram", {})
    assert histogram.get(str(int(expected_coverage))) == 1
    assert coverage.get("total_reads") == int(expected_coverage)
