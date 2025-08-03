import importlib
import genecoder.random_utils as random_utils


def test_global_rng_reproducible(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "123")
    mod = importlib.reload(random_utils)

    seq1 = [mod.make_rng().random() for _ in range(3)]
    seq2 = [mod.make_rng().random() for _ in range(3)]
    assert seq1 != seq2

    mod = importlib.reload(random_utils)
    seq1_again = [mod.make_rng().random() for _ in range(3)]
    seq2_again = [mod.make_rng().random() for _ in range(3)]

    assert seq1 == seq1_again
    assert seq2 == seq2_again
