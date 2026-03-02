from __future__ import annotations

from pathlib import Path

import pytest

from genecoder.core import run_pipeline
from genecoder.plugin_manager import CODEC_REGISTRY, init_plugins
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.sdk.plugins import Codec
from genecoder.simulators.illumina import IlluminaChannel
from genecoder.reed_solomon_codec import _HAS_REEDSOLO


class _Base4Codec(Codec):
    def encode(self, data: bytes) -> str:  # type: ignore[override]
        from genecoder.encoders import encode_base4_direct
        return encode_base4_direct(data)  # type: ignore[return-value]

    def decode(self, encoded: str) -> bytes:  # type: ignore[override]
        from genecoder.encoders import decode_base4_direct
        return decode_base4_direct(encoded)[0]


@pytest.mark.skipif(not _HAS_REEDSOLO, reason="reedsolo not installed")
def test_rs_illumina_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    init_plugins()
    CODEC_REGISTRY["base4"] = {"encode": _Base4Codec().encode, "decode": _Base4Codec().decode}
    SIMULATOR_REGISTRY["illumina"] = IlluminaChannel()

    data = b"illumina rs pipeline"
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    result, metrics = run_pipeline("base4", "reed_solomon", "illumina", str(inp), str(outp))

    assert result == data
    assert outp.read_bytes() == data
    violations = metrics.get("constraint_violations")
    if isinstance(violations, dict):
        assert violations.get("count") == 0
        assert violations.get("violations") == []
    else:
        assert violations == 0
