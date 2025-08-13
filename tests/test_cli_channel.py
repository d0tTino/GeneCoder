import os
import argparse
import json
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
            "apply",
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
    assert "substitutions" in data["metrics"]
    assert "insertions" in data["metrics"]
    assert "deletions" in data["metrics"]


def test_cli_illumina_rates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_fasta = tmp_path / "in_rates.fasta"
    create_fasta(input_fasta)
    output_fasta = tmp_path / "out_rates.fasta"
    called: list[tuple[float, float, float]] = []

    from genecoder.simulators.illumina import IlluminaChannel

    def fake_simulate(self: IlluminaChannel, seq: str) -> str:
        called.append((self.substitution_rate, self.insertion_rate, self.deletion_rate))
        return seq

    monkeypatch.setattr(IlluminaChannel, "simulate", fake_simulate)

    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

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
            "--illumina-sub-rate",
            "0.2",
            "--illumina-ins-rate",
            "0.3",
            "--illumina-del-rate",
            "0.1",
            "--min-length",
            "1",
        ],
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert called == [(0.2, 0.3, 0.1)]


def test_cli_illumina_profile_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_fasta = tmp_path / "in_profile_path.fasta"
    create_fasta(input_fasta)
    output_fasta = tmp_path / "out_profile_path.fasta"
    profile = tmp_path / "illumina.json"
    params = {
        "substitution_rate": 0.11,
        "insertion_rate": 0.02,
        "deletion_rate": 0.03,
        "read_length": 110,
        "coverage": 2,
    }
    profile.write_text(json.dumps(params))
    called: list[tuple[float, float, float, int, int]] = []

    from genecoder.simulators.illumina import IlluminaChannel

    def fake_simulate(self: IlluminaChannel, seq: str) -> str:
        called.append(
            (
                self.substitution_rate,
                self.insertion_rate,
                self.deletion_rate,
                self.read_length,
                self.coverage,
            )
        )
        return seq

    monkeypatch.setattr(IlluminaChannel, "simulate", fake_simulate)

    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

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
            params["read_length"],
            params["coverage"],
        )
    ]


def test_cli_illumina_profile_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_fasta = tmp_path / "in_profile_name.fasta"
    create_fasta(input_fasta)
    output_fasta = tmp_path / "out_profile_name.fasta"
    called: list[tuple[float, float, float, int, int]] = []

    from genecoder.simulators.illumina import IlluminaChannel, ILLUMINA_PROFILES

    def fake_simulate(self: IlluminaChannel, seq: str) -> str:
        called.append(
            (
                self.substitution_rate,
                self.insertion_rate,
                self.deletion_rate,
                self.read_length,
                self.coverage,
            )
        )
        return seq

    monkeypatch.setattr(IlluminaChannel, "simulate", fake_simulate)

    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

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
            "--illumina-profile",
            "miseq",
            "--min-length",
            "1",
        ],
        env=env,
    )
    assert result.returncode == 0, result.stderr
    params = ILLUMINA_PROFILES["miseq"]
    assert called == [
        (
            params["substitution_rate"],
            params["insertion_rate"],
            params["deletion_rate"],
            params["read_length"],
            params["coverage"],
        )
    ]


def test_cli_nanopore_rates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_fasta = tmp_path / "in_np_rates.fasta"
    create_fasta(input_fasta)
    output_fasta = tmp_path / "out_np_rates.fasta"
    called: list[tuple[float, float, float]] = []

    from genecoder.simulators.nanopore import NanoporeChannel

    def fake_simulate(self: NanoporeChannel, seq: str) -> str:
        called.append((self.substitution_rate, self.insertion_rate, self.deletion_rate))
        return seq

    monkeypatch.setattr(NanoporeChannel, "simulate", fake_simulate)

    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    result = run_cli_command(
        [
            "channel",
            "apply",
            "--input-file",
            str(input_fasta),
            "--output-file",
            str(output_fasta),
            "--simulator",
            "nanopore_d2sim",
            "--nanopore-sub-rate",
            "0.2",
            "--nanopore-ins-rate",
            "0.3",
            "--nanopore-del-rate",
            "0.1",
            "--min-length",
            "1",
        ],
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert called == [(0.2, 0.3, 0.1)]


def test_cli_indel_rates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_fasta = tmp_path / "in_indel.fasta"
    create_fasta(input_fasta)
    output_fasta = tmp_path / "out_indel.fasta"
    called: list[tuple[float, float, float]] = []

    from genecoder.error_simulation import Channel as IndelChannel

    def fake_simulate(self: IndelChannel, seq: str) -> str:
        called.append((self.substitution_prob, self.insertion_prob, self.deletion_prob))
        return seq

    monkeypatch.setattr(IndelChannel, "simulate", fake_simulate)

    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    result = run_cli_command(
        [
            "channel",
            "apply",
            "--input-file",
            str(input_fasta),
            "--output-file",
            str(output_fasta),
            "--simulator",
            "indel",
            "--sub-rate",
            "0.1",
            "--ins-rate",
            "0.2",
            "--del-rate",
            "0.05",
            "--min-length",
            "1",
        ],
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert called == [(0.1, 0.2, 0.05)]


def test_cli_indel_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_fasta = tmp_path / "in_indel_profile.fasta"
    create_fasta(input_fasta)
    output_fasta = tmp_path / "out_indel_profile.fasta"
    called: list[tuple[float, float, float]] = []

    from genecoder.error_simulation import Channel as IndelChannel, INDEL_PROFILES

    def fake_simulate(self: IndelChannel, seq: str) -> str:
        called.append((self.substitution_prob, self.insertion_prob, self.deletion_prob))
        return seq

    monkeypatch.setattr(IndelChannel, "simulate", fake_simulate)

    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    result = run_cli_command(
        [
            "channel",
            "apply",
            "--input-file",
            str(input_fasta),
            "--output-file",
            str(output_fasta),
            "--simulator",
            "indel",
            "--indel-profile",
            "illumina",
            "--min-length",
            "1",
        ],
        env=env,
    )
    assert result.returncode == 0, result.stderr
    prof = INDEL_PROFILES["illumina"]
    assert called == [(
        prof["substitution_prob"],
        prof["insertion_prob"],
        prof["deletion_prob"],
    )]


def test_channel_cli_yaml(tmp_path: Path) -> None:
    input_fasta = tmp_path / "in.fasta"
    create_fasta(input_fasta)
    config = tmp_path / "cfg.yml"
    config.write_text(
        """simulators:\n  - name: simple\nsynthesis:\n  min_length: 1\n  max_length: 10\n  max_homopolymer: 5\n"""
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
            "apply",
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
            "apply",
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
            "apply",
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
        "apply",
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
        "apply",
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
    assert "substitutions" in data["metrics"]
    assert "insertions" in data["metrics"]
    assert "deletions" in data["metrics"]


def test_channel_cli_bad_yaml(tmp_path: Path) -> None:
    """Malformed YAML configuration results in an error."""
    input_fasta = tmp_path / "in_bad.fasta"
    create_fasta(input_fasta)
    cfg = tmp_path / "bad.yml"
    cfg.write_text("simulators: [simple")

    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    result = run_cli_command(
        [
            "channel",
            "apply",
            "--input-file",
            str(input_fasta),
            "--output-file",
            str(tmp_path / "out_bad.fasta"),
            "--config",
            str(cfg),
        ],
        env=env,
    )
    assert result.returncode != 0
    assert "Invalid YAML" in result.stderr


def test_channel_cli_wrong_type(tmp_path: Path) -> None:
    """Wrong data types in YAML config are rejected."""
    input_fasta = tmp_path / "in_type.fasta"
    create_fasta(input_fasta)
    cfg = tmp_path / "type.yml"
    cfg.write_text("simulators: 1\n")

    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    result = run_cli_command(
        [
            "channel",
            "apply",
            "--input-file",
            str(input_fasta),
            "--output-file",
            str(tmp_path / "out_type.fasta"),
            "--config",
            str(cfg),
        ],
        env=env,
    )
    assert result.returncode != 0
    assert "'simulators' must be a list" in result.stderr


def test_cli_channel_profile_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_fasta = tmp_path / "in_profile.fasta"
    create_fasta(input_fasta)
    output_fasta = tmp_path / "out_profile.fasta"

    from genecoder.simulators.illumina import IlluminaChannel, ILLUMINA_PROFILES

    called: list[tuple[float, float, float]] = []

    def fake_simulate(self: IlluminaChannel, seq: str) -> str:
        called.append((self.substitution_rate, self.insertion_rate, self.deletion_rate))
        return seq

    monkeypatch.setattr(IlluminaChannel, "simulate", fake_simulate)

    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    result = run_cli_command(
        [
            "channel",
            "apply",
            "--input-file",
            str(input_fasta),
            "--output-file",
            str(output_fasta),
            "--profile",
            "miseq",
            "--min-length",
            "1",
        ],
        env=env,
    )
    assert result.returncode == 0, result.stderr
    expected = ILLUMINA_PROFILES["miseq"]
    assert called == [
        (
            expected["substitution_rate"],
            expected["insertion_rate"],
            expected["deletion_rate"],
        )
    ]
