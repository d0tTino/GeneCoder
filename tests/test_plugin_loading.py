from genecoder import CODEC_REGISTRY, FEC_REGISTRY, SIMULATOR_REGISTRY


def test_reverse_codec_plugin_loaded():
    assert "reverse" in CODEC_REGISTRY
    codec = CODEC_REGISTRY["reverse"]
    encoded = codec["encode"](b"abc")
    assert encoded == "cba"
    assert codec["decode"](encoded) == b"abc"


def test_fec_plugins_registered():
    assert "reed_solomon" in FEC_REGISTRY
    assert "ldpc" in FEC_REGISTRY
    assert "fountain" in FEC_REGISTRY


def test_simulator_plugins_registered():
    for name in ["none", "nanopore", "dnarsim", "squigulator"]:
        assert name in SIMULATOR_REGISTRY
