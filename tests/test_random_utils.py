import random
import logging
from genecoder.random_utils import make_rng


def test_make_rng_from_env(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "42")
    rng = make_rng()
    assert isinstance(rng, random.Random)
    assert rng.random() == random.Random(42).random()


def test_make_rng_without_env(monkeypatch):
    monkeypatch.delenv("GENECODER_SIM_SEED", raising=False)
    rng = make_rng()
    assert isinstance(rng, random.Random)
    assert 0.0 <= rng.random() < 1.0


def test_make_rng_invalid_env(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)
    monkeypatch.setenv("GENECODER_SIM_SEED", "invalid")
    rng = make_rng()
    assert isinstance(rng, random.Random)
    assert any(
        "Invalid GENECODER_SIM_SEED" in record.message for record in caplog.records
    )
