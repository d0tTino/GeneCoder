import json
import os
from pathlib import Path
from tests.test_cli import run_cli_command


def create_fasta(path: Path, seq: str = "ACGT", header: str = "seq") -> None:
    from src.genecoder.formats import to_fasta
    path.write_text(to_fasta(seq, header))


def test_channel_cli_simulator(tmp_path: Path) -> None:
    input_fasta = tmp_path / "in.fasta"
    create_fasta(input_fasta)
    output_fasta = tmp_path / "out.fasta"
    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"
    result = run_cli_command(
        [
            "channel",
            "--input-file",
            str(input_fasta),
            "--output-file",
            str(output_fasta),
            "--simulator",
            "simple",
            "--min-length",
            "1",
        ],
        env=env,
    )
    assert result.returncode == 0, result.stderr
    manifest = tmp_path / "out.manifest.json"
    data = json.loads(manifest.read_text())
    assert data["simulators"] == ["simple"]
    assert isinstance(data["metrics"].get("length"), int)


def test_channel_cli_yaml(tmp_path: Path) -> None:
    input_fasta = tmp_path / "in.fasta"
    create_fasta(input_fasta)
    config = tmp_path / "cfg.yml"
    config.write_text(
        """simulators:\n  - simple\nconstraints:\n  min_length: 1\n  max_length: 10\n  max_homopolymer: 5\n"""
    )
    output_fasta = tmp_path / "out2.fasta"
    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"
    result = run_cli_command(
        [
            "channel",
            "--input-file",
            str(input_fasta),
            "--output-file",
            str(output_fasta),
            "--config",
            str(config),
        ],
        env=env,
    )
    assert result.returncode == 0, result.stderr
    manifest = tmp_path / "out2.manifest.json"
    data = json.loads(manifest.read_text())
    assert data["simulators"] == ["simple"]
    assert data["constraints"]["max_homopolymer"] == 5

