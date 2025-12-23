from __future__ import annotations

import random
from pathlib import Path
from typing import Mapping

import pytest

from genecoder.core import run_pipeline
from genecoder.plugin_manager import (
    CODEC_REGISTRY,
    register_fec,
    register_simulator,
    init_plugins,
)
from genecoder.api import Codec
from genecoder.fountain_codec import (
    FountainFEC,
    droplet_batch_to_bytes,
    encode_data_fountain,
)
from genecoder.simulators.illumina import IlluminaChannel
from genecoder.formats import SequenceBatch


class _Base4Codec(Codec):
    def encode(self, data: bytes) -> str:  # type: ignore[override]
        from genecoder.encoders import encode_base4_direct
        return encode_base4_direct(data)  # type: ignore[return-value]

    def decode(self, encoded: str) -> bytes:  # type: ignore[override]
        from genecoder.encoders import decode_base4_direct
        return decode_base4_direct(encoded)[0]


def _subset_batch(
    batch: SequenceBatch,
    info: Mapping[str, object],
    keep_fraction: float,
    *,
    rng: random.Random | None = None,
) -> SequenceBatch:
    rng = rng or random.Random(1)
    total = len(batch.oligos)
    if total == 0:
        return SequenceBatch(batch_id=batch.batch_id, metadata=dict(batch.metadata), seed=batch.seed, oligos=[])
    k = int(info.get("k", 0))
    keep = max(k, int(round(total * keep_fraction)))
    keep = min(keep, total)
    indices = sorted(rng.sample(range(total), keep))
    required = set(range(min(k, total)))
    selected = set(indices)
    missing = sorted(required - selected)
    if missing:
        extras = sorted(selected - required, reverse=True)
        for idx in missing:
            if len(selected) >= keep and extras:
                removed = extras.pop(0)
                selected.remove(removed)
            selected.add(idx)
        indices = sorted(selected)
    survivors = [batch.oligos[i] for i in indices]
    return SequenceBatch(batch_id=batch.batch_id, metadata=dict(batch.metadata), seed=batch.seed, oligos=list(survivors))


class _DroppingFountainFEC(FountainFEC):
    def __init__(self, keep_fraction: float) -> None:
        super().__init__()
        self._keep_fraction = keep_fraction

    def encode(
        self,
        data: bytes,
        /,
        *,
        chunk_size: int = 4,
        seed: int = 0,
        redundancy: float = 2.0,
        droplet_count: int | None = None,
        c: float = 0.1,
        delta: float = 0.5,
        manifest_path: str | None = None,
        **kwargs: object,
    ) -> tuple[bytes, Mapping[str, object]]:
        batch, info = encode_data_fountain(
            data,
            chunk_size,
            seed=seed,
            redundancy=redundancy,
            droplet_count=droplet_count,
            c=c,
            delta=delta,
            manifest_path=manifest_path,
        )
        survivors = _subset_batch(batch, info, self._keep_fraction)
        updated_info = dict(info)
        updated_info["droplet_count"] = len(survivors.oligos)
        return droplet_batch_to_bytes(survivors), updated_info


def test_fountain_illumina_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    init_plugins()
    CODEC_REGISTRY["base4"] = {
        "encode": _Base4Codec().encode,
        "decode": _Base4Codec().decode,
    }
    register_fec("test_fountain", _DroppingFountainFEC(keep_fraction=0.85))
    register_simulator("test_illumina", IlluminaChannel())

    data = b"illumina"
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    result, _ = run_pipeline(
        "base4",
        "test_fountain",
        "test_illumina",
        str(inp),
        str(outp),
    )
    assert result == data
    assert outp.read_bytes() == data
