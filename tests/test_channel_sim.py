from genecoder.simulators import simulate_reads
from genecoder.encoders import encode_base4_direct, decode_base4_direct
from genecoder.error_correction import encode_triple_repeat, decode_triple_repeat


def test_simulate_errors_deterministic(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "0")
    assert simulate_reads("AAAA", "simple", error_rate=1.0) == "CGCC"


def test_decode_recovery_with_triple_repeat(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "42")
    data = b"hello"
    dna = encode_base4_direct(data)
    dna_tr = encode_triple_repeat(dna)
    corrupted = simulate_reads(dna_tr, "simple", error_rate=0.05)
    corrected, _, _ = decode_triple_repeat(corrupted)
    recovered, _ = decode_base4_direct(corrected)
    assert recovered == data
