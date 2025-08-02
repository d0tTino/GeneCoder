import os
from pathlib import Path

import pytest
from tests.test_cli import run_cli_command


def create_fasta(path: Path, seq: str = "ACGT", header: str = "seq") -> None:
    from src.genecoder.formats import to_fasta
    path.write_text(to_fasta(seq, header))


def _make_env() -> dict[str, str]:
    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"
    return env


def test_cli_quality_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_fasta = tmp_path / "in.fasta"
    create_fasta(input_fasta)
    output_fasta = tmp_path / "out.fasta"
    called: list[tuple[tuple[float, ...] | None, int]] = []

    from genecoder.simulators.illumina import IlluminaChannel

    def fake_simulate(self: IlluminaChannel, seq: str) -> str:
        called.append((self.quality_profile, self.coverage))
        return seq

    monkeypatch.setattr(IlluminaChannel, "simulate", fake_simulate)

    env = _make_env()
    result = run_cli_command(
        [
            "channel",
            "apply",
            "--input-file",
            str(input_fasta),
            "--output-file",
            str(output_fasta),
            "--simulator",
            "illumina",
            "--quality-profile",
            "0.1,0.2,0.3",
            "--min-length",
            "1",
        ],
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert called == [((0.1, 0.2, 0.3), 1)]


def test_cli_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_fasta = tmp_path / "in.fasta"
    create_fasta(input_fasta)
    output_fasta = tmp_path / "out.fasta"
    called: list[tuple[tuple[float, ...] | None, int]] = []

    from genecoder.simulators.illumina import IlluminaChannel

    def fake_simulate(self: IlluminaChannel, seq: str) -> str:
        called.append((self.quality_profile, self.coverage))
        return seq

    monkeypatch.setattr(IlluminaChannel, "simulate", fake_simulate)

    env = _make_env()
    result = run_cli_command(
        [
            "channel",
            "apply",
            "--input-file",
            str(input_fasta),
            "--output-file",
            str(output_fasta),
            "--simulator",
            "illumina",
            "--coverage",
            "5",
            "--min-length",
            "1",
        ],
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert called == [(None, 5)]
