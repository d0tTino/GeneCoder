import random

from genecoder.simulators.nanopore import (
    NanoporeChannel,
    NanoporeDNArSimChannel,
    _mutate_read,
)


def _const_rng() -> random.Random:
    rng = random.Random()
    rng.random = lambda: 0.05
    return rng


def test_simulate_fallback_homopolymer_deletion() -> None:
    rng = _const_rng()
    assert NanoporeDNArSimChannel._simulate_fallback("AAAAT", 0.1, rng) == "AAAT"

    rng = _const_rng()
    assert NanoporeDNArSimChannel._simulate_fallback("AAAT", 0.1, rng) == "AAAT"


def test_mutate_read_homopolymer_deletion() -> None:
    rng = _const_rng()
    channel = NanoporeChannel(
        substitution_rate=0.0, insertion_rate=0.0, deletion_rate=0.03
    )
    assert _mutate_read("AAAAT", None, rng, channel) == "AAAT"

    rng = _const_rng()
    assert _mutate_read("AAAT", None, rng, channel) == "AAAT"

