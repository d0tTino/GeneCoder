from genecoder import insilicoseq_adapter, desp_adapter


def _sub_rate(original: str, mutated: str) -> float:
    changes = sum(1 for a, b in zip(original, mutated) if a != b)
    return changes / len(original)


def test_insilicoseq_stats(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    seq = "ACGTACGTACGT"
    out = insilicoseq_adapter.simulate_insilicoseq(seq, error_rate=0.2)
    assert out == "ACGTCCCTTCGT"
    assert _sub_rate(seq, out) == 3 / len(seq)


def test_desp_stats(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    seq = "ACGTACGTACGT"
    out = desp_adapter.simulate_desp(seq, error_rate=0.2)
    assert out == "TCGTACATACGT"
    assert _sub_rate(seq, out) == 2 / len(seq)
