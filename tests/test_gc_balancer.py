from genecoder.gc_balancer import AdvancedGCBalancer
from genecoder.gc_constrained_encoder import calculate_gc_content
from genecoder.utils import get_max_homopolymer_length
import pytest


def test_gc_balancer_roundtrip():
    balancer = AdvancedGCBalancer(0.4, 0.6, 3)
    dna = balancer.encode(b"\x05\x05\x05\x05")
    decoded = balancer.decode(dna)
    assert decoded == b"\x05\x05\x05\x05"


def test_gc_balancer_enforces_constraints():
    balancer = AdvancedGCBalancer(0.25, 0.75, 3, window_size=8, step_size=4)
    dna = balancer.encode(b"\x05" * 8)
    windows = []
    if len(dna) < 8:
        windows.append(dna)
    else:
        for i in range(0, len(dna) - 8 + 1, 4):
            windows.append(dna[i : i + 8])
    for window in windows:
        assert 0.25 <= calculate_gc_content(window) <= 0.75
        assert get_max_homopolymer_length(window) <= 3


def test_gc_balancer_encode_raises_on_violation():
    balancer = AdvancedGCBalancer(0.4, 0.6, 2, window_size=4, step_size=1)
    with pytest.raises(ValueError):
        balancer.encode(b"\x00\x00")


def test_gc_balancer_decode_checks_constraints():
    balancer = AdvancedGCBalancer(0.4, 0.6, 3, window_size=5, step_size=5)
    with pytest.raises(ValueError):
        balancer.decode("AAAAA")


def test_gc_balancer_stream_roundtrip():
    balancer = AdvancedGCBalancer(0.4, 0.6, 3)
    chunks = [b"\x05", b"\x05", b"\x05", b"\x05"]
    dna_chunks = list(balancer.encode(chunks, stream=True))
    decoded_iter = balancer.decode(dna_chunks, stream=True)
    decoded = b"".join(decoded_iter)
    assert decoded == b"\x05\x05\x05\x05"


def test_gc_balancer_stream_violation():
    balancer = AdvancedGCBalancer(0.4, 0.6, 2, window_size=4, step_size=1)
    with pytest.raises(ValueError):
        list(balancer.encode([b"\x00", b"\x00"], stream=True))


def test_gc_balancer_stream_decode_checks():
    balancer = AdvancedGCBalancer(0.4, 0.6, 3, window_size=5, step_size=5)
    with pytest.raises(ValueError):
        list(balancer.decode(["AAAAA"], stream=True))
