import random
from genecoder.random_utils import make_rng


def test_make_rng_from_env(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "42")
    rng = make_rng()
    assert isinstance(rng, random.Random)
    assert rng.random() == random.Random(42).random()
