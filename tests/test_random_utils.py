import importlib
import random
import logging
import genecoder.random_utils as random_utils


def test_make_rng_from_env(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "42")
    mod = importlib.reload(random_utils)
    rng = mod.make_rng()
    assert isinstance(rng, random.Random)
    assert rng.random() == random.Random(42).random()


def test_make_rng_without_env(monkeypatch):
    monkeypatch.delenv("GENECODER_SIM_SEED", raising=False)
    mod = importlib.reload(random_utils)
    rng = mod.make_rng()
    assert isinstance(rng, random.Random)
    assert 0.0 <= rng.random() < 1.0


def test_make_rng_invalid_env(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)
    monkeypatch.setenv("GENECODER_SIM_SEED", "invalid")
    mod = importlib.reload(random_utils)
    rng = mod.make_rng()
    assert isinstance(rng, random.Random)
    assert any(
        "Invalid GENECODER_SIM_SEED" in record.message for record in caplog.records
    )
