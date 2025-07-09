import json
import os
import argparse
from pathlib import Path

import pytest
from tests.test_cli import run_cli_command
from src.genecoder.cli.channel import _handle_command

yaml = pytest.importorskip("yaml")


def create_fasta(path: Path, seq: str = "ACGT", header: str = "seq") -> None:
    from src.genecoder.formats import to_fasta
    path.write_text(to_fasta(seq, header))


def create_multi_fasta(path: Path, records: list[tuple[str, str]]) -> None:
    from src.genecoder.formats import to_fasta
    path.write_text("".join(to_fasta(seq, hdr) for seq, hdr in records))


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


def test_channel_cli_multi_record(tmp_path: Path) -> None:
    input_fasta = tmp_path / "in_multi.fasta"
    create_multi_fasta(input_fasta, [("AAAA", "seq1"), ("TTTT", "seq2")])
    output_fasta = tmp_path / "out_multi.fasta"
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
    from src.genecoder.formats import from_fasta
    parsed = from_fasta(output_fasta.read_text())
    assert [hdr for hdr, _ in parsed] == ["seq1", "seq2"]


def test_channel_cli_threads_and_processes_error(tmp_path: Path) -> None:
    input_fasta = tmp_path / "in_tp.fasta"
    create_fasta(input_fasta)
    output_fasta = tmp_path / "out_tp.fasta"
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
            "--threads",
            "2",
            "--processes",
            "2",
        ],
        env=env,
    )
    assert result.returncode != 0
    assert "Cannot specify both --threads and --processes" in result.stderr


def test_handle_command_threads_processes_error(tmp_path: Path) -> None:
    input_fasta = tmp_path / "in.fasta"
    create_fasta(input_fasta)
    args = argparse.Namespace(
        simulators=["simple"],
        input_file=str(input_fasta),
        output_file=str(tmp_path / "out.fasta"),
        sub_prob=0.0,
        ins_prob=0.0,
        del_prob=0.0,
        seed=None,
        parallel=False,
        threads=1,
        processes=1,
        config=None,
        min_length=1,
        max_length=300,
        max_homopolymer=4,
    )
    with pytest.raises(SystemExit):
        _handle_command(args)


@pytest.mark.parametrize(
    "parallel,threads,processes",
    [
        (True, None, None),
        (True, 2, None),
        (True, None, 2),
        (False, 2, None),
        (False, None, 2),
    ],
)
def test_channel_cli_parallel_variants(
    tmp_path: Path, parallel: bool, threads: int | None, processes: int | None
) -> None:
    input_fasta = tmp_path / "seq.fasta"
    create_fasta(input_fasta)

    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    baseline = tmp_path / "baseline.fasta"
    base_cmd = [
        "channel",
        "--input-file",
        str(input_fasta),
        "--output-file",
        str(baseline),
        "--simulator",
        "simple",
        "--min-length",
        "1",
    ]
    result_base = run_cli_command(base_cmd, env=env)
    assert result_base.returncode == 0, result_base.stderr
    from src.genecoder.formats import from_fasta

    expected_seq = from_fasta(baseline.read_text())[0][1]

    out = tmp_path / f"out_{parallel}_{threads}_{processes}.fasta"
    cmd = [
        "channel",
        "--input-file",
        str(input_fasta),
        "--output-file",
        str(out),
        "--simulator",
        "simple",
        "--min-length",
        "1",
    ]
    if parallel:
        cmd.append("--parallel")
    if threads is not None:
        cmd.extend(["--threads", str(threads)])
    if processes is not None:
        cmd.extend(["--processes", str(processes)])

    result = run_cli_command(cmd, env=env)
    assert result.returncode == 0, result.stderr

    seq = from_fasta(out.read_text())[0][1]
    assert seq == expected_seq

    manifest = tmp_path / f"out_{parallel}_{threads}_{processes}.manifest.json"
    data = json.loads(manifest.read_text())
    assert data["simulators"] == ["simple"]
    assert data["metrics"]["length"] == len(seq)

