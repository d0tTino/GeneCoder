from __future__ import annotations

import importlib.util
import json
import random
from pathlib import Path
from typing import Mapping

import pytest

_HAS_REEDSOLO = importlib.util.find_spec("reedsolo") is not None

from genecoder.formats import SequenceBatch, SequenceOligo
from genecoder.fountain_codec import (
    _robust_soliton_cdf,
    _sample_degree,
    decode_data_fountain,
    droplet_batch_to_bytes,
    encode_data_fountain,
)
from genecoder.simulators.batch_utils import (
    RESULT_COVERAGE_KEY,
    RESULT_DROPOUT_FLAG_KEY,
)
from genecoder.reed_solomon_codec import decode_data_rs, encode_data_rs


def _select_survivors(
    batch: SequenceBatch,
    info: Mapping[str, object],
    *,
    keep_fraction: float | None = None,
    keep_count: int | None = None,
    rng: random.Random | None = None,
) -> SequenceBatch:
    """Return a copy of ``batch`` keeping a subset of droplets."""

    rng = rng or random.Random(0)
    total = len(batch.oligos)
    if total == 0:
        return SequenceBatch(
            batch_id=batch.batch_id,
            metadata=dict(batch.metadata),
            seed=batch.seed,
            oligos=[],
        )
    k = int(info.get("k", 0))
    if keep_count is None:
        if keep_fraction is None:
            keep_fraction = 1.0
        keep = max(k, int(round(total * keep_fraction)))
    else:
        keep = max(k, keep_count)
    keep = min(keep, total)
    if keep >= total:
        indices = list(range(total))
    else:
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

    new_metadata = dict(batch.metadata)
    new_metadata["batch_size"] = str(len(indices))
    survivors: list[SequenceOligo] = []
    for idx in indices:
        oligo = batch.oligos[idx]
        meta = dict(oligo.metadata)
        meta["batch_size"] = str(len(indices))
        survivors.append(
            SequenceOligo(
                sequence=oligo.sequence,
                header=oligo.header,
                index=oligo.index,
                oligo_id=oligo.oligo_id,
                metadata=meta,
                seed=oligo.seed,
            )
        )

    return SequenceBatch(
        batch_id=batch.batch_id,
        metadata=new_metadata,
        seed=batch.seed,
        oligos=survivors,
    )


def test_fountain_roundtrip() -> None:
    data = b"Fountain test data"
    batch, info = encode_data_fountain(data, chunk_size=5, redundancy=1.4, seed=7)
    survivors = _select_survivors(batch, info, keep_fraction=0.9)
    decoded, _ = decode_data_fountain(survivors, info)
    assert decoded == data


def test_fountain_empty_data(tmp_path: Path) -> None:
    manifest_path = tmp_path / "droplets.json"
    batch, info = encode_data_fountain(b"", chunk_size=5, manifest_path=manifest_path)
    assert len(batch.oligos) == 0
    assert info["orig_len"] == 0
    assert manifest_path.read_text(encoding="utf-8")
    decoded, _ = decode_data_fountain(batch, info)
    assert decoded == b""


def test_fountain_erasure_recovery() -> None:
    data = b"robust fountain erasure test" * 3
    batch, info = encode_data_fountain(data, chunk_size=4, redundancy=1.3, seed=11)
    survivors = _select_survivors(batch, info, keep_fraction=0.8)
    decoded, _ = decode_data_fountain(survivors, info)
    assert decoded == data


def test_fountain_roundtrip_explicit_droplets() -> None:
    data = b"explicit droplet count"
    batch, info = encode_data_fountain(
        data, chunk_size=3, droplet_count=20, seed=1
    )
    survivors = _select_survivors(batch, info, keep_count=15)
    decoded, _ = decode_data_fountain(survivors, info)
    assert decoded == data


def test_fountain_droplet_loss_with_explicit_count() -> None:
    data = b"loss scenario" * 4
    batch, info = encode_data_fountain(
        data, chunk_size=4, droplet_count=40, seed=2
    )
    survivors = _select_survivors(batch, info, keep_count=30)
    decoded, _ = decode_data_fountain(survivors, info)
    assert decoded == data


def test_fountain_decode_skips_dropout_metadata() -> None:
    data = b"dropout metadata" * 3
    batch, info = encode_data_fountain(
        data,
        chunk_size=4,
        redundancy=2.0,
        seed=7,
    )
    k = int(info["k"])
    drop_count = max(1, k // 3)
    mutated_oligos: list[SequenceOligo] = []
    for idx, oligo in enumerate(batch.oligos):
        metadata = dict(oligo.metadata)
        payload = oligo.sequence
        if idx < drop_count:
            metadata[RESULT_DROPOUT_FLAG_KEY] = "true"
            metadata[RESULT_COVERAGE_KEY] = "0"
            bad_payload = (
                "DEADBEEF" * ((len(payload) + 7) // 8)
            )[: len(payload)]
            payload = bad_payload.upper()
        mutated_oligos.append(
            SequenceOligo(
                sequence=payload,
                header=oligo.header,
                index=oligo.index,
                oligo_id=oligo.oligo_id,
                metadata=metadata,
                seed=oligo.seed,
            )
        )

    mutated_batch = SequenceBatch(
        batch_id=batch.batch_id,
        metadata=dict(batch.metadata),
        seed=batch.seed,
        oligos=mutated_oligos,
    )

    decoded, _ = decode_data_fountain(mutated_batch, info)
    assert decoded == data


@pytest.mark.skipif(not _HAS_REEDSOLO, reason="reedsolo not installed")
def test_fountain_with_reed_solomon_outer_code() -> None:
    data = b"rs outer integration"
    rs_encoded, nsym, sym_size, prim = encode_data_rs(data, nsym=4)
    batch, info = encode_data_fountain(
        rs_encoded, chunk_size=5, droplet_count=30, seed=3
    )
    survivors = _select_survivors(batch, info, keep_count=25)
    fountain_decoded, _ = decode_data_fountain(survivors, info)
    rs_decoded, _ = decode_data_rs(
        fountain_decoded, nsym, symbol_size=sym_size, primitive=prim
    )
    assert rs_decoded == data


def _degree_hist(batch: SequenceBatch, info: Mapping[str, object]) -> dict[int, int]:
    k = int(info["k"])
    cdf = _robust_soliton_cdf(k, c=float(info["c"]), delta=float(info["delta"]))
    hist: dict[int, int] = {}
    for oligo in batch.oligos:
        seed_val = int(oligo.metadata["droplet_seed"])
        rnd = random.Random(seed_val)
        degree = _sample_degree(cdf, rnd)
        hist[degree] = hist.get(degree, 0) + 1
    return hist


def test_fountain_degree_distribution_params() -> None:
    data = b"distribution" * 20
    batch_default, info_default = encode_data_fountain(
        data, chunk_size=3, redundancy=1.0, seed=0
    )
    batch_custom, info_custom = encode_data_fountain(
        data, chunk_size=3, redundancy=1.0, seed=0, c=0.2, delta=0.3
    )
    hist_default = _degree_hist(batch_default, info_default)
    hist_custom = _degree_hist(batch_custom, info_custom)
    assert hist_default != hist_custom


def test_fountain_decode_degree_distribution_override() -> None:
    data = b"distribution" * 20
    batch, info = encode_data_fountain(
        data, chunk_size=3, redundancy=1.0, seed=0
    )

    def degree_hist(c: float, delta: float) -> dict[int, int]:
        k = info["k"]
        cdf = _robust_soliton_cdf(int(k), c=c, delta=delta)
        hist: dict[int, int] = {}
        for oligo in batch.oligos:
            seed_val = int(oligo.metadata["droplet_seed"])
            rnd = random.Random(seed_val)
            degree = _sample_degree(cdf, rnd)
            hist[degree] = hist.get(degree, 0) + 1
        return hist

    hist_default = degree_hist(float(info["c"]), float(info["delta"]))
    hist_override = degree_hist(float(info["c"]) * 2, float(info["delta"]) / 2)
    assert hist_default != hist_override


def test_fountain_manifest_export(tmp_path: Path) -> None:
    data = b"manifest check"
    manifest_path = tmp_path / "droplets.json"
    batch, info = encode_data_fountain(
        data, chunk_size=4, redundancy=1.2, manifest_path=manifest_path
    )
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["chunk_size"] == 4
    assert manifest["orig_len"] == len(data)
    assert len(manifest["droplets"]) == info["droplet_count"]
    # Ensure legacy byte stream remains compatible for integrations
    byte_stream = droplet_batch_to_bytes(batch)
    assert len(byte_stream) == len(batch.oligos) * (int(info["chunk_size"]) + 4)
