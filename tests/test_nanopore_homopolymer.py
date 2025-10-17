from __future__ import annotations

import random
from typing import Tuple

from genecoder.simulators.nanopore import NanoporeChannel
from genecoder.simulators.nanopore_batch import mutate_read
from genecoder.simulators.nanopore_profiles import split_context_indels


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


def test_insertion_profile_distribution() -> None:
    channel = NanoporeChannel(
        substitution_rate=0.0,
        insertion_rate=0.0,
        deletion_rate=0.0,
        insertion_profile={5: 0.5},
    )
    ins_rate, _ = _simulate_many(channel, "AAAAA")
    assert 0.4 < ins_rate < 0.6


def test_deletion_profile_distribution() -> None:
    channel = NanoporeChannel(
        substitution_rate=0.0,
        insertion_rate=0.0,
        deletion_rate=0.0,
        deletion_profile={5: 0.5},
    )
    _, del_rate = _simulate_many(channel, "AAAAA")
    assert 0.4 < del_rate < 0.6


def test_long_homopolymer_has_higher_error_rate() -> None:
    ctx_ins, ctx_del = split_context_indels(
        {"AA": {1: 0.05, 5: 0.8}}, "context_indels"
    )
    channel = NanoporeChannel(
        substitution_rate=0.0,
        insertion_rate=0.0,
        deletion_rate=0.0,
        context_insertions=ctx_ins,
        context_deletions=ctx_del,
    )
    short_ins, short_del = _simulate_many(channel, "AA")
    long_ins, long_del = _simulate_many(channel, "AAAAA")
    assert long_ins > short_ins
    assert long_del > short_del

