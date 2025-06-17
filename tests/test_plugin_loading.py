from genecoder import CODEC_REGISTRY


def test_reverse_codec_plugin_loaded():
    assert "reverse" in CODEC_REGISTRY
    codec = CODEC_REGISTRY["reverse"]
    encoded = codec["encode"](b"abc")
    assert encoded == "cba"
    assert codec["decode"](encoded) == b"abc"
