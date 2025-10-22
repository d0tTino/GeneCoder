from __future__ import annotations

from pathlib import Path

import pytest

import genecoder.chamaeleo_codec as cc


def _fake_encode(
    _method: object,
    input_path: str,
    output_path: str,
    *,
    need_index: bool = False,
    segment_length: int = 48,
) -> None:  # noqa: ARG001
    data = Path(input_path).read_bytes()
    Path(output_path).write_text(data.hex())


def _fake_decode(
    _method: object,
    *,
    input_path: str,
    output_path: str,
    has_index: bool = False,
) -> None:  # noqa: ARG001
    text = Path(input_path).read_text()
    Path(output_path).write_bytes(bytes.fromhex(text))


@pytest.mark.parametrize("codec_name", cc.SUPPORTED_CHAMAELEO_CODECS)
def test_chamaeleo_roundtrip(codec_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure each Chamaeleo codec round-trips successfully."""

    monkeypatch.setattr(cc, "_ce", _fake_encode, raising=False)
    monkeypatch.setattr(cc, "_cd", _fake_decode, raising=False)
    monkeypatch.setattr(cc, "_HAS_CHAMAELEO", True)
    monkeypatch.setattr(cc, "_METHOD_INSTANCES", {})
    cc._method_class.cache_clear()

    codec_cls = cc._CODECS[codec_name]
    codec = codec_cls()
    method_token = object()
    cc._METHOD_INSTANCES[codec_name] = method_token

    data = b"roundtrip test"
    encoded = codec.encode(data)
    decoded = codec.decode(encoded)
    assert decoded == data

    if codec_name == "chamaeleo_gc":
        monkeypatch.setattr(cc, "_DEFAULT_CODEC", cc._CODECS["chamaeleo_gc"]())
        cc._METHOD_INSTANCES["chamaeleo_gc"] = method_token
        encoded_default = cc.encode_chamaeleo(data)
        decoded_default = cc.decode_chamaeleo(encoded_default)
        assert decoded_default == data
