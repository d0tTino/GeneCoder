from __future__ import annotations

import random
from pathlib import Path
from typing import Tuple

import pytest

from genecoder.simulators.nanopore import NanoporeChannel
from genecoder.simulators.nanopore_batch import mutate_read


def _simulate_many(
    channel: NanoporeChannel, sequence: str, runs: int = 1000
) -> Tuple[float, float]:
    rng = random.Random(0)
    ins = 0
    dels = 0
    for _ in range(runs):
        mutated = mutate_read(sequence, None, rng, channel)
        if len(mutated) > len(sequence):
            ins += 1
        if len(mutated) < len(sequence):
            dels += 1
    return ins / runs, dels / runs


@pytest.mark.parametrize(
    "sequence, expected_bias",
    [("AAAAA", True), ("ACGTACGT", False)],
)
def test_context_indel_rates(tmp_path: Path, sequence: str, expected_bias: bool) -> None:
    profile_path = tmp_path / "nanopore_context.yaml"
    profile_path.write_text(
        "substitution_rate: 0.0\n"
        "insertion_rate: 0.0\n"
        "deletion_rate: 0.0\n"
        "context_indels:\n"
        "  AA:\n"
        "    5:\n"
        "      insertions: 0.5\n"
        "      deletions: 0.5\n"
    )
    channel = NanoporeChannel(profile_path=str(profile_path))

    ins_rate, del_rate = _simulate_many(channel, sequence)
    control_ins, control_del = _simulate_many(channel, "ACGTACGT")

    if expected_bias:
        assert ins_rate > control_ins
        assert del_rate > control_del
    else:
        assert ins_rate <= control_ins
        assert del_rate <= control_del


def test_builtin_profile_context_bias() -> None:
    channel = NanoporeChannel(profile="minion")
    poly_ins, poly_del = _simulate_many(channel, "AAAAA")
    control_ins, control_del = _simulate_many(channel, "ACGTACGT")
    assert poly_ins > control_ins
    assert poly_del > control_del
