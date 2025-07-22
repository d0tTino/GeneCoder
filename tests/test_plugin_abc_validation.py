import pytest
import genecoder.plugin_manager as plugins


def test_register_codec_requires_subclass() -> None:
    with pytest.raises(TypeError):
        plugins.register_codec("bad", object())


def test_register_fec_requires_subclass() -> None:
    with pytest.raises(TypeError):
        plugins.register_fec("bad", object())


def test_register_simulator_requires_subclass() -> None:
    with pytest.raises(TypeError):
        plugins.register_simulator("bad", object())
