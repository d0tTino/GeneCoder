import os
from pathlib import Path

import pytest
import random
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


def _count_mutations(channel, seq: str, replicates: int = 100, seed: int = 42) -> list[int]:
    counts = [0] * len(seq)
    for i in range(replicates):
        rng = random.Random(seed + i)
        mutated = channel._mutate_read(seq, channel.quality_profile, rng)
        for idx, (a, b) in enumerate(zip(seq, mutated)):
            if a != b:
                counts[idx] += 1
    return counts


def test_per_base_quality_profile_mutation_rates() -> None:
    from genecoder.simulators.illumina import IlluminaChannel

    seq = "AAAAA"
    base = IlluminaChannel(
        substitution_rate=0.2, insertion_rate=0.0, deletion_rate=0.0, read_length=len(seq)
    )
    quality = IlluminaChannel(
        substitution_rate=0.2,
        insertion_rate=0.0,
        deletion_rate=0.0,
        read_length=len(seq),
        quality_profile=[0.0, 0.0, 1.0, 0.0, 0.0],
    )
    base_counts = _count_mutations(base, seq)
    quality_counts = _count_mutations(quality, seq)
    assert quality_counts[2] == 100  # third base always mutates
    assert base_counts[2] < 100
    assert quality_counts[0] == 0 < base_counts[0]


def test_context_specific_errors_mutation_rates() -> None:
    from genecoder.simulators.illumina import IlluminaChannel

    seq = "AAAAA"
    base = IlluminaChannel(
        substitution_rate=0.2, insertion_rate=0.0, deletion_rate=0.0, read_length=len(seq)
    )
    context = IlluminaChannel(
        substitution_rate=0.2,
        insertion_rate=0.0,
        deletion_rate=0.0,
        read_length=len(seq),
        context_errors={"AA": 0.0},
    )
    base_counts = _count_mutations(base, seq)
    context_counts = _count_mutations(context, seq)
    assert all(c == 0 for c in context_counts[1:])
    assert all(c > 0 for c in base_counts[1:])


@pytest.mark.parametrize(
    "preset, expected",
    [("miseq", "MiSeq"), ("hiseq", "HiSeq")],
)
def test_insilicoseq_presets(monkeypatch: pytest.MonkeyPatch, preset: str, expected: str) -> None:
    from genecoder import insilicoseq_adapter

    called: list[str | None] = []

    def fake_sim(seq: str, error_rate: float = 0.05, profile: str | None = None) -> str:
        called.append(profile)
        return seq

    monkeypatch.setattr(insilicoseq_adapter, "_simulate_insilicoseq", fake_sim)

    insilicoseq_adapter.simulate_insilicoseq("ACGT", profile=preset)
    assert called == [expected]
