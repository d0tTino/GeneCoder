import random
from genecoder.simulators.illumina import IlluminaChannel
from genecoder.simulators.nanopore import (
    NanoporeChannel,
    NanoporeDNArSimChannel,
    _mutate_read,
)


def test_illumina_simulate_seed(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "123")
    ch = IlluminaChannel(
        substitution_rate=0.2,
        insertion_rate=0.1,
        deletion_rate=0.1,
        read_length=10,
    )
    result = ch.simulate("ACGTACGTACGT")
    assert result == "ATTACTTC"


def test_nanopore_simulate_fallback_seed() -> None:
    rng = random.Random(123)
    result = NanoporeDNArSimChannel._simulate_fallback("ACGTACGT", 0.1, rng)
    assert result == "ACGTCCGGT"


def test_nanopore_mutate_read_seed() -> None:
    rng = random.Random(123)
    channel = NanoporeChannel(
        substitution_rate=0.1,
        insertion_rate=0.1,
        deletion_rate=0.1,
    )
    result = _mutate_read("ACGTACGT", None, rng, channel)
    assert result == "GACTTG"
