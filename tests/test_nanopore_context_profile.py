import random
from pathlib import Path

from genecoder.simulators.nanopore import NanoporeChannel, _mutate_read


def _simulate_many(channel: NanoporeChannel, sequence: str, runs: int = 1000) -> tuple[float, float]:
    rng = random.Random(0)
    ins = 0
    dels = 0
    for _ in range(runs):
        mutated = _mutate_read(sequence, None, rng, channel)
        if len(mutated) > len(sequence):
            ins += 1
        if len(mutated) < len(sequence):
            dels += 1
    return ins / runs, dels / runs


def test_context_indel_rates(tmp_path: Path) -> None:
    prof = tmp_path / "nanopore_context.yaml"
    prof.write_text(
        "substitution_rate: 0.0\n"
        "insertion_rate: 0.0\n"
        "deletion_rate: 0.0\n"
        "context_indels:\n"
        "  AA:\n"
        "    5:\n"
        "      insertions: 0.5\n"
        "      deletions: 0.5\n"
    )
    channel = NanoporeChannel(profile_path=str(prof))

    poly_ins, poly_del = _simulate_many(channel, "AAAAA")
    control_ins, control_del = _simulate_many(channel, "ACGTACGT")
    assert poly_ins > control_ins
    assert poly_del > control_del
