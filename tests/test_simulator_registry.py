from genecoder.simulators import SIMULATOR_REGISTRY, simulate_reads


def test_illumina_registered_and_deterministic(monkeypatch):
    assert "illumina" in SIMULATOR_REGISTRY
    seq = "A" * 50
    monkeypatch.setenv("GENECODER_SIM_SEED", "123")
    first = simulate_reads(seq, "illumina")
    monkeypatch.setenv("GENECODER_SIM_SEED", "123")
    second = simulate_reads(seq, "illumina")
    assert first == second
    assert isinstance(first, str)

