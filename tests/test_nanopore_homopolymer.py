import random

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

