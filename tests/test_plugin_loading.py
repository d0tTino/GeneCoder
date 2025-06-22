from genecoder import (
    CODEC_REGISTRY,
    FEC_REGISTRY,
    SIMULATOR_REGISTRY,
    load_plugins,
)

load_plugins()


def test_reverse_codec_plugin_loaded() -> None:
    assert "reverse" in CODEC_REGISTRY
    codec = CODEC_REGISTRY["reverse"]
    encoded = codec["encode"](b"abc")
    assert encoded == "cba"
    assert codec["decode"](encoded) == b"abc"


def test_fec_plugins_registered() -> None:
    assert "reed_solomon" in FEC_REGISTRY
    assert "ldpc" in FEC_REGISTRY
    assert "fountain" in FEC_REGISTRY
    assert "bch" in FEC_REGISTRY
    assert "raptorq" in FEC_REGISTRY


def test_simulator_plugins_registered() -> None:
    from genecoder.channels.base import BaseChannel

    assert isinstance(SIMULATOR_REGISTRY, dict)
    assert all(isinstance(ch, BaseChannel) for ch in SIMULATOR_REGISTRY.values())

