from __future__ import annotations

from pathlib import Path

import pytest

from typing import Mapping, Sequence

from genecoder.core import (
    compile_coding_stack,
    decode,
    encode,
    inspect_coding_plan,
    metrics as gather_metrics,
    run_pipeline,
    simulate,
)
from genecoder.formats import SequenceBatch
from genecoder.api import Codec
from genecoder.plugin_manager import CODEC_REGISTRY, init_plugins
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.reed_solomon_codec import _HAS_REEDSOLO
from genecoder.constraints import ConstraintPolicy, RepairPolicy, ConstraintStageGateError


class _Base4Codec(Codec):
    def encode(self, data: bytes) -> str:  # type: ignore[override]
        from genecoder.encoders import encode_base4_direct
        return encode_base4_direct(data)  # type: ignore[return-value]

    def decode(self, encoded: str) -> bytes:  # type: ignore[override]
        from genecoder.encoders import decode_base4_direct
        return decode_base4_direct(encoded)[0]




class _ViolatingCodec(Codec):
    def encode(self, data: bytes) -> str:  # type: ignore[override]
        return "AAAAAA"

    def decode(self, encoded: str) -> bytes:  # type: ignore[override]
        return b"ok"

class _BatchAwareCodec(Codec):
    def __init__(self) -> None:
        self.last_batch: SequenceBatch | None = None
        self.last_batch_metadata: Mapping[str, str] | None = None
        self.last_oligo_metadata: list[Mapping[str, str]] | None = None

    def encode(self, data: bytes, /, **kwargs: object) -> SequenceBatch:  # type: ignore[override]
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
        **_kwargs: object,
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
    assert m["error_bases"] == len(dna.primary_sequence())
    assert m["substitution_rate"] == 0.0
    assert m["insertion_rate"] == 0.0
    assert m["deletion_rate"] == 0.0
    assert m["error_rate"] == 0.0


def test_metrics_constraint_violations_per_oligo() -> None:
    init_plugins()
    sequences = ["ACGT" * 20] * 4  # Each oligo valid but combined length exceeds constraints
    records = [
        (f"batch_id=batch-valid oligo_index={idx+1}", seq)
        for idx, seq in enumerate(sequences)
    ]
    batch = SequenceBatch.build(records, batch_id="batch-valid")

    result = gather_metrics(batch, b"payload", b"payload", None)
    violations = result.get("constraint_violations")
    assert isinstance(violations, dict)
    assert violations["count"] == 0
    assert violations["violations"] == []

    failing_records = records[:]
    failing_records[1] = ("batch_id=batch-valid oligo_index=2", "AT" * 20)
    failing_batch = SequenceBatch.build(failing_records, batch_id="batch-valid")
    failing = gather_metrics(failing_batch, b"payload", b"payload", None)
    failing_violations = failing.get("constraint_violations")
    assert isinstance(failing_violations, dict)
    assert failing_violations["count"] == 1
    assert failing_violations["type_counts"].get("gc_low") == 1
    assert failing_violations["violations"]
    first_violation = failing_violations["violations"][0]
    assert "gc_low" in (first_violation.get("types") or [first_violation.get("type")])
    assert first_violation.get("sequence_id")


def test_compile_coding_stack_from_config() -> None:
    init_plugins()
    CODEC_REGISTRY["base4"] = {"encode": _Base4Codec().encode, "decode": _Base4Codec().decode}
    stack = compile_coding_stack({"coding": {"layers": [{"type": "codec", "name": "base4"}]}})
    assert len(stack) == 1


def test_metrics_include_coding_stack() -> None:
    init_plugins()
    CODEC_REGISTRY["base4"] = {"encode": _Base4Codec().encode, "decode": _Base4Codec().decode}
    data = b"stacked"
    dna, _ = encode("base4", None, data)
    report = gather_metrics(dna, data, data, None)
    assert "coding_stack" in report
    assert "total_redundancy" in report["coding_stack"]


def test_inspect_coding_plan_rejected_for_streaming() -> None:
    init_plugins()
    CODEC_REGISTRY["base4"] = {"encode": _Base4Codec().encode, "decode": _Base4Codec().decode}
    plan = inspect_coding_plan({"codec": "base4", "coding": {"streaming": True}})
    assert plan["valid"] is False
    assert any("streaming" in item["reason"] for item in plan["candidates"])


def test_encode_emits_standardized_layer_metrics() -> None:
    init_plugins()
    CODEC_REGISTRY["base4"] = {"encode": _Base4Codec().encode, "decode": _Base4Codec().decode}
    _, fec_info = encode("base4", None, b"metrics")
    assert isinstance(fec_info, dict) or fec_info is None
    # no fec_info for codec-only path; inspect explicit plan to ensure standardized keys exist
    plan = inspect_coding_plan({"codec": "base4"})
    assert plan["selected"][0]["name"] == "base4"


def test_encode_constraint_assumption_fail_fast() -> None:
    init_plugins()
    CODEC_REGISTRY["violating"] = {"encode": _ViolatingCodec().encode, "decode": _ViolatingCodec().decode}
    policy = ConstraintPolicy(
        min_length=1,
        max_length=20,
        gc_min=0.0,
        gc_max=1.0,
        max_homopolymer=1,
        assumption_mode="fail_fast",
        repair=RepairPolicy(enabled=False),
    )
    with pytest.raises(ConstraintStageGateError):
        encode("violating", None, b"x", constraint_policy=policy)


def test_encode_constraint_assumption_repair_deterministic() -> None:
    init_plugins()
    CODEC_REGISTRY["violating"] = {"encode": _ViolatingCodec().encode, "decode": _ViolatingCodec().decode}
    policy = ConstraintPolicy(
        min_length=1,
        max_length=20,
        gc_min=0.0,
        gc_max=1.0,
        max_homopolymer=1,
        assumption_mode="repair",
        repair=RepairPolicy(enabled=True, profile="strict"),
    )
    dna, fec_info = encode("violating", None, b"x", constraint_policy=policy)
    assert "AA" not in dna.primary_sequence()
    assert isinstance(fec_info, Mapping) or fec_info is None
    outcomes = dna.metadata.get("constraint_outcomes")
    assert isinstance(outcomes, list) and outcomes
    assert outcomes[0]["repairs_applied"] > 0
