from __future__ import annotations

from pathlib import Path

import pytest

from genecoder.core import encode, simulate, decode, metrics as gather_metrics, run_pipeline
from genecoder.formats import SequenceBatch
from genecoder.api import Codec
from genecoder.plugin_manager import CODEC_REGISTRY, init_plugins
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.reed_solomon_codec import _HAS_REEDSOLO


class _Base4Codec(Codec):
    def encode(self, data: bytes) -> str:  # type: ignore[override]
        from genecoder.encoders import encode_base4_direct
        return encode_base4_direct(data)  # type: ignore[return-value]

    def decode(self, encoded: str) -> bytes:  # type: ignore[override]
        from genecoder.encoders import decode_base4_direct
        return decode_base4_direct(encoded)[0]


def test_roundtrip_rs_simple(tmp_path: Path) -> None:
    if not _HAS_REEDSOLO:
        pytest.skip("reedsolo not installed")

    init_plugins()
    CODEC_REGISTRY["base4"] = {"encode": _Base4Codec().encode, "decode": _Base4Codec().decode}
    SIMULATOR_REGISTRY["simple"] = type(SIMULATOR_REGISTRY["simple"])(error_rate=0.0)

    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    data = b"pipeline test"
    inp.write_bytes(data)

    result, metrics = run_pipeline("base4", "reed_solomon", "simple", str(inp), str(outp))
    assert result == data
    assert metrics["gc_content"] >= 0.0
    assert outp.read_bytes() == data


def test_encode_helper() -> None:
    init_plugins()
    CODEC_REGISTRY["base4"] = {"encode": _Base4Codec().encode, "decode": _Base4Codec().decode}
    expected = _Base4Codec().encode(b"hi")
    dna, fec_info = encode("base4", None, b"hi")
    assert isinstance(dna, SequenceBatch)
    assert dna.primary_sequence() == expected
    assert fec_info is None


def test_simulate_helper() -> None:
    dna, subs, ins, dels, coverage = simulate(None, "ACGT")
    assert dna == "ACGT"
    assert subs is ins is dels is None
    assert coverage is None


def test_decode_helper() -> None:
    init_plugins()
    CODEC_REGISTRY["base4"] = {"encode": _Base4Codec().encode, "decode": _Base4Codec().decode}
    dna, fec_info = encode("base4", None, b"data")
    assert decode("base4", None, dna, fec_info) == b"data"


def test_metrics_helper() -> None:
    init_plugins()
    CODEC_REGISTRY["base4"] = {"encode": _Base4Codec().encode, "decode": _Base4Codec().decode}
    data = b"metrics"
    dna, _ = encode("base4", None, data)
    m = gather_metrics(dna, data, data, None)
    assert m["decode_success_rate"] == 1.0
    assert "gc_content" in m
    assert m["oligo_metrics"]["dropout_flags"] == [False]
    assert m["oligo_metrics"]["coverage"] == [None]
