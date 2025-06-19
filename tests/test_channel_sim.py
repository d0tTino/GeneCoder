import random
from genecoder.channel_sim import simulate_errors
from genecoder.encoders import encode_base4_direct, decode_base4_direct
from genecoder.error_correction import encode_triple_repeat, decode_triple_repeat


def test_simulate_errors_deterministic():
    rng = random.Random(0)
    assert simulate_errors("AAAA", 1.0, rng=rng) == "CGCC"


def test_decode_recovery_with_triple_repeat():
    rng = random.Random(42)
    data = b"hello"
    dna = encode_base4_direct(data)
    dna_tr = encode_triple_repeat(dna)
    corrupted = simulate_errors(dna_tr, 0.05, rng=rng)
    corrected, _, _ = decode_triple_repeat(corrupted)
    recovered, _ = decode_base4_direct(corrected)
    assert recovered == data
