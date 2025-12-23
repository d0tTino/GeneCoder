from __future__ import annotations

import random

from genecoder.simulators.illumina import IlluminaChannel
from genecoder.simulators.nanopore import NanoporeChannel
from genecoder.simulators.nanopore_batch import mutate_read
from genecoder.simulators.nanopore_external import simulate_simple_model


def test_illumina_simulate_seed(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "123")
    ch = IlluminaChannel(
        substitution_rate=0.2,
        insertion_rate=0.1,
        deletion_rate=0.1,
        read_length=10,
        coverage=5,
    )
    result = ch.simulate("ACGTACGTACGT")
    assert result == "TCTGGATTA"


def test_nanopore_simulate_fallback_seed() -> None:
    rng = random.Random(123)
    result = simulate_simple_model("ACGTACGT", 0.1, rng)
    assert result == "ACGTCCGGT"


def test_nanopore_mutate_read_seed() -> None:
    rng = random.Random(123)
    channel = NanoporeChannel(
        substitution_rate=0.1,
        insertion_rate=0.1,
        deletion_rate=0.1,
    )
    result = mutate_read("ACGTACGT", None, rng, channel)
    assert result == "GACTTG"
