from genecoder.simulators.decay import DegradationChannel


def test_decay_deterministic_seed(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "123")
    ch = DegradationChannel(deletion_prob=0.0, substitution_prob=0.5)
    first = ch.simulate("ACGTACGT")
    monkeypatch.setenv("GENECODER_SIM_SEED", "123")
    ch2 = DegradationChannel(deletion_prob=0.0, substitution_prob=0.5)
    second = ch2.simulate("ACGTACGT")
    assert first == second == "CACACCGC"


def test_decay_strand_loss(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    ch = DegradationChannel(deletion_prob=1.0, substitution_prob=0.0)
    assert ch.simulate("ACGT") == ""
