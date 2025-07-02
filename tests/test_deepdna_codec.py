import importlib
import sys
import types

import pytest


def _install_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = types.ModuleType("deepdna")

    class DeepDNA:
        def __init__(self, model_name: str):
            self.model_name = model_name

        def encode(self, data: bytes) -> bytes:  # type: ignore[override]
            return data[::-1]

        def decode(self, encoded: bytes) -> bytes:  # type: ignore[override]
            return encoded[::-1]

    mod.DeepDNA = DeepDNA
    monkeypatch.setitem(sys.modules, "deepdna", mod)


def test_deepdna_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_stub(monkeypatch)
    import genecoder.deepdna_codec as deepdna_codec

    importlib.reload(deepdna_codec)

    data = b"deepdna test"
    encoded, info = deepdna_codec.encode_data_deepdna(data)
    decoded, corrected = deepdna_codec.decode_data_deepdna(encoded, info)
    assert decoded == data
    assert corrected == 0
