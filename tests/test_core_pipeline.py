from __future__ import annotations

from pathlib import Path

import pytest

from typing import Any, Mapping, Sequence

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


class _BatchAwareCodec(Codec):
    def __init__(self) -> None:
        self.last_batch: SequenceBatch | None = None
        self.last_batch_metadata: Mapping[str, str] | None = None
        self.last_oligo_metadata: list[Mapping[str, str]] | None = None

    def encode(self, data: bytes, /, **kwargs: Any) -> SequenceBatch:  # type: ignore[override]
        from genecoder.encoders import encode_base4_direct

        dna = encode_base4_direct(data)
        half = max(1, len(dna) // 2)
        records = [
            ("batch_id=batchy oligo_index=1", dna[:half]),
            ("batch_id=batchy oligo_index=2", dna[half:]),
        ]
        return SequenceBatch.build(records, batch_id="batchy", batch_seed=11)

    def decode(
        self,
        encoded: SequenceBatch,
        /,
        *,
        batch_metadata: Mapping[str, str] | None = None,
        oligo_metadata: Sequence[Mapping[str, str]] | None = None,
        **_kwargs: Any,
    ) -> bytes:  # type: ignore[override]
        from genecoder.encoders import decode_base4_direct

        self.last_batch = encoded
        self.last_batch_metadata = dict(batch_metadata or {})
        self.last_oligo_metadata = [dict(m) for m in (oligo_metadata or [])]
        return decode_base4_direct(encoded.primary_sequence())[0]


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


def test_decode_helper_sequence_batch_metadata() -> None:
    init_plugins()
    codec = _BatchAwareCodec()
    CODEC_REGISTRY["batchy"] = {"encode": codec.encode, "decode": codec.decode}

    payload = b"batch aware payload"
    dna, fec_info = encode("batchy", None, payload)
    assert isinstance(dna, SequenceBatch)

    result = decode("batchy", None, dna, fec_info)
    assert result == payload
    assert codec.last_batch is dna
    assert codec.last_batch_metadata == dict(dna.metadata)
    assert codec.last_oligo_metadata == [dict(ol.metadata) for ol in dna.oligos]


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
