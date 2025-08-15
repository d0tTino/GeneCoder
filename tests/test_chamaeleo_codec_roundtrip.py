from __future__ import annotations

from pathlib import Path

import pytest

from genecoder.chamaeleo_codec import decode_chamaeleo, encode_chamaeleo


def test_chamaeleo_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure encode_chamaeleo followed by decode_chamaeleo is lossless."""

    def fake_ce(
        _method: object,
        input_path: str,
        output_path: str,
        *,
        need_index: bool = False,
        segment_length: int = 48,
    ) -> None:  # noqa: ARG001
        data = Path(input_path).read_bytes()
        Path(output_path).write_text(data.hex())

    def fake_cd(
        _method: object,
        *,
        input_path: str,
        output_path: str,
        has_index: bool = False,
    ) -> None:  # noqa: ARG001
        text = Path(input_path).read_text()
        Path(output_path).write_bytes(bytes.fromhex(text))

    monkeypatch.setattr("genecoder.chamaeleo_codec._ce", fake_ce, raising=False)
    monkeypatch.setattr("genecoder.chamaeleo_codec._cd", fake_cd, raising=False)
    monkeypatch.setattr("genecoder.chamaeleo_codec._HAS_CHAMAELEO", True)
    monkeypatch.setattr("genecoder.chamaeleo_codec._method", object())

    data = b"roundtrip test"
    encoded = encode_chamaeleo(data)
    decoded = decode_chamaeleo(encoded)
    assert decoded == data
