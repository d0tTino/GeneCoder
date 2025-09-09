import os
from pathlib import Path
import pytest
import yaml
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


def test_insilicoseq_cli_profile_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_fasta = tmp_path / "in.fasta"
    create_fasta(input_fasta)
    output_fasta = tmp_path / "out.fasta"
    profile = tmp_path / "insilicoseq.yml"
    params = {
        "substitution_rate": 0.05,
        "insertion_rate": 0.0001,
        "deletion_rate": 0.0001,
        "read_length": 110,
        "coverage": 2,
    }
    profile.write_text(yaml.safe_dump(params))

    called: list[tuple[float, float, float]] = []
    import genecoder.simulators.illumina as illumina
    from genecoder.simulators.illumina import IlluminaChannel

    monkeypatch.setattr(illumina.shutil, "which", lambda _: None)

    def fake_simulate(self: IlluminaChannel, seq: str) -> str:
        called.append((self.substitution_rate, self.insertion_rate, self.deletion_rate))
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
            "illumina_insilicoseq",
            "--illumina-profile",
            str(profile),
            "--min-length",
            "1",
        ],
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert called == [
        (
            params["substitution_rate"],
            params["insertion_rate"],
            params["deletion_rate"],
        )
    ]
