import random
import logging

from genecoder.simulators.nanopore import NanoporeChannel, _mutate_read
from genecoder import nanopore_sim


def _count_substitutions(channel: NanoporeChannel, sequence: str, runs: int, seed: int) -> int:
    rng = random.Random(seed)
    subs = 0
    for _ in range(runs):
        mutated = _mutate_read(sequence, None, rng, channel)
        subs += sum(a != b for a, b in zip(mutated, sequence))
    return subs


def _count_ins_del(channel: NanoporeChannel, sequence: str, runs: int, seed: int) -> tuple[int, int]:
    rng = random.Random(seed)
    ins = dels = 0
    for _ in range(runs):
        mutated = _mutate_read(sequence, None, rng, channel)
        if len(mutated) > len(sequence):
            ins += 1
        elif len(mutated) < len(sequence):
            dels += 1
    return ins, dels


def test_defaults_without_profiles() -> None:
    seq = "ACGTACGT"
    ch_default = NanoporeChannel()
    ch_empty = NanoporeChannel(context_errors={}, insertion_profile={}, deletion_profile={})
    rng1 = random.Random(0)
    rng2 = random.Random(0)
    mutated_default = _mutate_read(seq, None, rng1, ch_default)
    mutated_empty = _mutate_read(seq, None, rng2, ch_empty)
    assert mutated_default == mutated_empty == seq
    assert ch_default.context_errors == {}
    assert ch_default.insertion_profile == {}
    assert ch_default.deletion_profile == {}


def test_context_profile_increases_substitutions() -> None:
    seq = "ACACACAC"
    base = NanoporeChannel(substitution_rate=0.1, insertion_rate=0.0, deletion_rate=0.0)
    ctx = NanoporeChannel(
        substitution_rate=0.1,
        insertion_rate=0.0,
        deletion_rate=0.0,
        context_errors={"AC": 2.0},
    )
    base_subs = _count_substitutions(base, seq, runs=200, seed=1)
    ctx_subs = _count_substitutions(ctx, seq, runs=200, seed=1)
    assert base_subs == 164
    assert ctx_subs == 239
    assert ctx_subs > base_subs


def test_homopolymer_profiles_affect_mutation_counts() -> None:
    seq = "AAAAA"
    runs = 200
    seed = 42
    ins_base, _ = _count_ins_del(
        NanoporeChannel(substitution_rate=0.0, insertion_rate=0.1, deletion_rate=0.0),
        seq,
        runs,
        seed,
    )
    ins_prof, _ = _count_ins_del(
        NanoporeChannel(
            substitution_rate=0.0,
            insertion_rate=0.1,
            deletion_rate=0.0,
            insertion_profile={5: 0.9},
        ),
        seq,
        runs,
        seed,
    )
    assert ins_base == 86
    assert ins_prof == 185
    assert ins_prof > ins_base

    _, del_base = _count_ins_del(
        NanoporeChannel(substitution_rate=0.0, insertion_rate=0.0, deletion_rate=0.1),
        seq,
        runs,
        seed,
    )
    _, del_prof = _count_ins_del(
        NanoporeChannel(
            substitution_rate=0.0,
            insertion_rate=0.0,
            deletion_rate=0.1,
            deletion_profile={5: 0.9},
        ),
        seq,
        runs,
        seed,
    )
    assert del_base == 84
    assert del_prof == 183
    assert del_prof > del_base


def test_context_insertion_profile_affect_counts() -> None:
    seq = "AAT"
    runs = 200
    seed = 7
    ins_base, _ = _count_ins_del(
        NanoporeChannel(substitution_rate=0.0, insertion_rate=0.0, deletion_rate=0.0),
        seq,
        runs,
        seed,
    )
    ins_ctx, _ = _count_ins_del(
        NanoporeChannel(
            substitution_rate=0.0,
            insertion_rate=0.0,
            deletion_rate=0.0,
            context_insertions={"AA": {1: 0.9}},
        ),
        seq,
        runs,
        seed,
    )
    assert ins_ctx > ins_base


def test_context_deletion_profile_affect_counts() -> None:
    seq = "TTA"
    runs = 200
    seed = 8
    _, del_base = _count_ins_del(
        NanoporeChannel(substitution_rate=0.0, insertion_rate=0.0, deletion_rate=0.0),
        seq,
        runs,
        seed,
    )
    _, del_ctx = _count_ins_del(
        NanoporeChannel(
            substitution_rate=0.0,
            insertion_rate=0.0,
            deletion_rate=0.0,
            context_deletions={"TT": {1: 0.9}},
        ),
        seq,
        runs,
        seed,
    )
    assert del_ctx > del_base


def test_homopolymer_weighting_in_fallback() -> None:
    runs = 200
    seed = 21
    table = {"substitution_rate": 0.0, "insertion_rate": 0.1, "deletion_rate": 0.1}

    def simulate_many(seq: str) -> tuple[int, int]:
        rng = random.Random(seed)
        ins = dels = 0
        for _ in range(runs):
            mutated = nanopore_sim._simulate_adapter(
                "dnarsim", seq, 0.0, rng, rate_table=table
            )
            if len(mutated) > len(seq):
                ins += 1
            elif len(mutated) < len(seq):
                dels += 1
        return ins, dels

    prev_level = nanopore_sim.logger.level
    try:
        nanopore_sim.logger.setLevel(logging.ERROR)
        ins_short, del_short = simulate_many("AAA")
        ins_long, del_long = simulate_many("AAAAAA")
        assert ins_short == 45
        assert del_short == 44
        assert ins_long == 54
        assert del_long == 86
        assert ins_long > ins_short
        assert del_long > del_short
    finally:
        nanopore_sim.logger.setLevel(prev_level)
