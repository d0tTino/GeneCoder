from genecoder.gc_balancer import AdvancedGCBalancer


def test_gc_balancer_roundtrip():
    balancer = AdvancedGCBalancer(0.4, 0.6, 3)
    dna = balancer.encode(b"abc")
    decoded = balancer.decode(dna)
    assert decoded == b"abc"
