from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

import genecoder.pipeline as pipeline_mod
from genecoder.pipeline import run_pipeline
from genecoder.api import Codec
from genecoder.encoders import decode_base4_direct, encode_base4_direct
from genecoder.formats import SequenceBatch
from genecoder.plugin_manager import CODEC_REGISTRY, FEC_REGISTRY, init_plugins
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.channel_sim import Channel
from genecoder.simulators.nanopore import NanoporeChannel
from genecoder.simulators.batch_utils import RESULT_DROPOUT_FLAG_KEY, RESULT_MUTATION_TOTALS_KEY
from genecoder.reed_solomon_codec import _HAS_REEDSOLO

SAMPLE_DATA = Path("tests/data/sample.txt")


class _BatchCodec(Codec):
    def __init__(self) -> None:
        self.extra_metadata: dict[str, str] = {}

    def encode(self, data: bytes, /, **_kwargs: object) -> SequenceBatch:  # type: ignore[override]
        dna_sequence = encode_base4_direct(data)
        header = "batch_id=legacy-batch input_file=tests/data/sample.txt"
        records = [
            (f"{header} oligo_index=1 sentinel=true", ""),
            (f"{header} oligo_index=2", dna_sequence),
        ]
        batch = SequenceBatch.build(records, batch_id="legacy-batch")
        if self.extra_metadata:
            batch.metadata.update({str(k): str(v) for k, v in self.extra_metadata.items()})
        return batch

    def decode(self, encoded: str, /, **_kwargs: object) -> bytes:  # type: ignore[override]
        return decode_base4_direct(encoded)[0]


@pytest.fixture()
def legacy_codec(monkeypatch: pytest.MonkeyPatch) -> tuple[str, _BatchCodec]:
    init_plugins()
    codec = _BatchCodec()
    codec_name = "legacy_batch_base4"
    monkeypatch.setitem(
        CODEC_REGISTRY,
        codec_name,
        {"encode": codec.encode, "decode": codec.decode},
    )

    def _fountain_encode(data: bytes, /, **_kwargs: object) -> tuple[bytes, dict[str, Any]]:
        length = len(data)
        info = {
            "orig_len": length,
            "chunk_size": max(1, length),
            "seed": 0,
            "batch_metadata": {"batch_id": "legacy-batch"},
        }
        return data, info

    def _fountain_decode(
        encoded: bytes,
        info: Mapping[str, Any],
        /,
        **_kwargs: object,
    ) -> tuple[bytes, int]:
        orig_len = int(info.get("orig_len", len(encoded)))
        return encoded[:orig_len], orig_len

    monkeypatch.setitem(
        FEC_REGISTRY,
        "fountain",
        {"encode": _fountain_encode, "decode": _fountain_decode},
    )
    return codec_name, codec


@pytest.mark.skipif(not _HAS_REEDSOLO, reason="reedsolo not installed")
def test_pipeline_legacy_reed_solomon_roundtrip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, legacy_codec: tuple[str, _BatchCodec]
) -> None:
    codec_name, codec = legacy_codec
    codec.extra_metadata.clear()
    monkeypatch.setenv("GENECODER_SIM_SEED", "5")
    monkeypatch.setitem(SIMULATOR_REGISTRY, "simple", Channel(error_rate=0.0))

    payload = SAMPLE_DATA.read_bytes()
    inp = tmp_path / "sample.bin"
    outp = tmp_path / "roundtrip.bin"
    inp.write_bytes(payload)

    decoded, metrics, fec_info = run_pipeline(
        codec_name,
        "reed_solomon",
        "simple",
        str(inp),
        str(outp),
    )

    assert decoded == payload
    assert outp.read_bytes() == payload
    assert metrics["gc_content"] >= 0.0
    assert fec_info is not None
    assert "nsym" in fec_info


def test_pipeline_legacy_fountain_nanopore_dropouts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, legacy_codec: tuple[str, _BatchCodec]
) -> None:
    codec_name, codec = legacy_codec
    monkeypatch.setenv("GENECODER_SIM_SEED", "9")

    class _DropoutNanopore(NanoporeChannel):
        def __init__(self) -> None:
            super().__init__(profile="rapid")
            self.error_rate = 0.0
            self.substitution_rate = 0.0
            self.insertion_rate = 0.0
            self.deletion_rate = 0.0

        def simulate(self, sequence: SequenceBatch | str) -> SequenceBatch | str:  # type: ignore[override]
            result = super().simulate(sequence)
            if isinstance(result, SequenceBatch) and result.oligos:
                result.oligos[0].metadata[RESULT_DROPOUT_FLAG_KEY] = "true"
            return result

    monkeypatch.setitem(SIMULATOR_REGISTRY, "nanopore", _DropoutNanopore())

    payload = SAMPLE_DATA.read_bytes()
    inp = tmp_path / "sample.bin"
    outp = tmp_path / "fountain.bin"
    inp.write_bytes(payload)

    decode_calls: list[SequenceBatch | str] = []
    original_decode = pipeline_mod.core.decode

    def _recording_decode(*args, **kwargs):  # type: ignore[no-untyped-def]
        decode_calls.append(args[2])
        return original_decode(*args, **kwargs)

    monkeypatch.setattr(pipeline_mod.core, "decode", _recording_decode)

    decoded, metrics, fec_info = run_pipeline(
        codec_name,
        "fountain",
        "nanopore",
        str(inp),
        str(outp),
    )

    assert decoded == payload
    assert outp.read_bytes() == payload
    assert len(decode_calls) == 1
    assert fec_info is not None
    channel_info = fec_info.get("channel") if isinstance(fec_info, Mapping) else None
    assert isinstance(channel_info, dict)
    dropout_info = channel_info.get("dropout")
    assert isinstance(dropout_info, dict)
    assert dropout_info.get("count", 0) >= 1
    assert 0.0 < float(dropout_info.get("fraction", 0.0)) <= 1.0
    assert channel_info.get("status") in {"success", "failed"}
    assert channel_info.get("decode_success_rate") == metrics.get("decode_success_rate")


@pytest.mark.parametrize("filter_mutated,expects_positive_mutation", [(False, True), (True, False)])
def test_pipeline_legacy_fountain_filter_mutated_controls_decode_input(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    legacy_codec: tuple[str, _BatchCodec],
    filter_mutated: bool,
    expects_positive_mutation: bool,
) -> None:
    codec_name, _codec = legacy_codec

    class _MutatedNanopore(NanoporeChannel):
        def __init__(self) -> None:
            super().__init__(profile="rapid")
            self.error_rate = 0.0
            self.substitution_rate = 0.0
            self.insertion_rate = 0.0
            self.deletion_rate = 0.0

        def simulate(self, sequence: SequenceBatch | str) -> SequenceBatch | str:  # type: ignore[override]
            result = super().simulate(sequence)
            if isinstance(result, SequenceBatch) and result.oligos:
                result.oligos[0].metadata[RESULT_MUTATION_TOTALS_KEY] = {
                    "substitutions": 1,
                    "insertions": 0,
                    "deletions": 0,
                }
                result.oligos[0].metadata[RESULT_DROPOUT_FLAG_KEY] = False
            return result

    monkeypatch.setitem(SIMULATOR_REGISTRY, "nanopore", _MutatedNanopore())

    payload = SAMPLE_DATA.read_bytes()
    inp = tmp_path / f"sample-{filter_mutated}.bin"
    outp = tmp_path / f"fountain-mutated-{filter_mutated}.bin"
    inp.write_bytes(payload)

    decode_calls: list[SequenceBatch | str] = []

    def _recording_decode(*args, **kwargs):  # type: ignore[no-untyped-def]
        decode_calls.append(args[2])
        return b"decoded"

    monkeypatch.setattr(pipeline_mod.core, "decode", _recording_decode)

    decoded, _metrics, _fec_info = run_pipeline(
        codec_name,
        "fountain",
        "nanopore",
        str(inp),
        str(outp),
        filter_mutated=filter_mutated,
    )

    assert decoded == b"decoded"
    assert len(decode_calls) == 1
    assert isinstance(decode_calls[0], SequenceBatch)
    decode_batch = decode_calls[0]
    positive_mutation_count = 0
    for oligo in decode_batch.oligos:
        mutation_data = oligo.metadata.get(RESULT_MUTATION_TOTALS_KEY)
        if not isinstance(mutation_data, dict):
            continue
        if int(mutation_data.get("substitutions", 0)) > 0:
            positive_mutation_count += 1

    assert (positive_mutation_count > 0) is expects_positive_mutation

def test_pipeline_legacy_fountain_keeps_mutated_oligos_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, legacy_codec: tuple[str, _BatchCodec]
) -> None:
    codec_name, codec = legacy_codec
    monkeypatch.setenv("GENECODER_SIM_SEED", "11")

    class _MutatedNanopore(NanoporeChannel):
        def __init__(self) -> None:
            super().__init__(profile="rapid")
            self.error_rate = 0.0
            self.substitution_rate = 0.0
            self.insertion_rate = 0.0
            self.deletion_rate = 0.0

        def simulate(self, sequence: SequenceBatch | str) -> SequenceBatch | str:  # type: ignore[override]
            result = super().simulate(sequence)
            if isinstance(result, SequenceBatch) and result.oligos:
                result.oligos[0].metadata[RESULT_MUTATION_TOTALS_KEY] = {
                    "substitutions": 1,
                    "insertions": 0,
                    "deletions": 0,
                }
            return result

    monkeypatch.setitem(SIMULATOR_REGISTRY, "nanopore", _MutatedNanopore())

    payload = SAMPLE_DATA.read_bytes()
    inp = tmp_path / "sample.bin"
    outp = tmp_path / "fountain-mutated.bin"
    inp.write_bytes(payload)

    decode_calls: list[SequenceBatch | str] = []
    original_decode = pipeline_mod.core.decode

    def _recording_decode(*args, **kwargs):  # type: ignore[no-untyped-def]
        decode_calls.append(args[2])
        return original_decode(*args, **kwargs)

    monkeypatch.setattr(pipeline_mod.core, "decode", _recording_decode)

    decoded, metrics, fec_info = run_pipeline(
        codec_name,
        "fountain",
        "nanopore",
        str(inp),
        str(outp),
    )

    assert decoded == payload
    assert outp.read_bytes() == payload
    assert len(decode_calls) == 1
    assert isinstance(decode_calls[0], SequenceBatch)
    decode_batch = decode_calls[0]
    assert any(
        RESULT_MUTATION_TOTALS_KEY in oligo.metadata for oligo in decode_batch.oligos
    )
    assert fec_info is not None
    assert metrics["gc_content"] >= 0.0
