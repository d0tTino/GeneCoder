from __future__ import annotations

from pathlib import Path

import pytest
import genecoder.simulators.nanopore as nanopore
import genecoder.simulators.nanopore_external as nanopore_external
from genecoder.core import run_pipeline
from genecoder.plugin_manager import CODEC_REGISTRY, init_plugins
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.api import Codec
from genecoder.reed_solomon_codec import _HAS_REEDSOLO


class _Base4Codec(Codec):
    def encode(self, data: bytes) -> str:  # type: ignore[override]
        from genecoder.encoders import encode_base4_direct
        return encode_base4_direct(data)  # type: ignore[return-value]

    def decode(self, encoded: str) -> bytes:  # type: ignore[override]
        from genecoder.encoders import decode_base4_direct
        return decode_base4_direct(encoded)[0]


@pytest.mark.skipif(not _HAS_REEDSOLO, reason="reedsolo not installed")
def test_rs_nanopore_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    fallback = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("fallback"))
    monkeypatch.setattr(nanopore_external, "run_dnarsim_cli", fallback)
    monkeypatch.setattr(nanopore, "run_dnarsim_cli", fallback)

    init_plugins()
    CODEC_REGISTRY["base4"] = {"encode": _Base4Codec().encode, "decode": _Base4Codec().decode}
    SIMULATOR_REGISTRY["nanopore"] = nanopore.NanoporeChannel(error_rate=0.1)

    data = b"nanopore rs pipeline"
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    result, metrics = run_pipeline("base4", "reed_solomon", "nanopore", str(inp), str(outp))

    assert result == data
    assert outp.read_bytes() == data
    assert isinstance(metrics.get("substitutions"), int)
    assert isinstance(metrics.get("insertions"), int)
    assert isinstance(metrics.get("deletions"), int)
