import random
from pathlib import Path

import yaml

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
    profile = {
        "substitution_rate": 0.0,
        "insertion_rate": 0.0,
        "deletion_rate": 0.0,
        "context_indels": {"AA": {5: {"insertions": 0.5, "deletions": 0.5}}},
    }
    prof = tmp_path / "nanopore_context.yaml"
    prof.write_text(yaml.safe_dump(profile))
    channel = NanoporeChannel(profile_path=str(prof))

    poly_ins, poly_del = _simulate_many(channel, "AAAAA")
    control_ins, control_del = _simulate_many(channel, "ACGTACGT")
    assert poly_ins > control_ins
    assert poly_del > control_del
