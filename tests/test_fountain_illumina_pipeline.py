from __future__ import annotations

from pathlib import Path

import pytest

from genecoder.core import run_pipeline
from genecoder.plugin_manager import CODEC_REGISTRY, init_plugins
from genecoder.api import Codec


class _Base4Codec(Codec):
    def encode(self, data: bytes) -> str:  # type: ignore[override]
        from genecoder.encoders import encode_base4_direct
        return encode_base4_direct(data)  # type: ignore[return-value]

    def decode(self, encoded: str) -> bytes:  # type: ignore[override]
        from genecoder.encoders import decode_base4_direct
        return decode_base4_direct(encoded)[0]


def test_fountain_illumina_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pytest.importorskip("pyfinite")
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    init_plugins()
    CODEC_REGISTRY["base4"] = {
        "encode": _Base4Codec().encode,
        "decode": _Base4Codec().decode,
    }

    data = b"fountain illumina pipeline"
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    result, _ = run_pipeline(
        "base4",
        "fountain",
        "illumina",
        str(inp),
        str(outp),
    )
    assert result == data
    assert outp.read_bytes() == data
