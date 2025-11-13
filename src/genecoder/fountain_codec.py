"""Luby Transform fountain code helpers.

This module implements a minimal Luby Transform (LT) fountain encoder and
decoder similar to the scheme used by DNA Fountain. Droplets are produced from
byte ``chunks`` of the input where each droplet stores a 32‑bit seed followed by
the XOR of a random subset of chunks chosen according to the robust soliton
distribution. Decoding recovers the original chunks using an iterative peeling
algorithm driven by the same seeds.
"""

# ruff: noqa: ANN401

from __future__ import annotations

from typing import Any, Mapping, Tuple, cast

from .api import FEC

import json
import math
import random
from collections import deque
from itertools import accumulate
from pathlib import Path

from .formats import SequenceBatch, SequenceOligo
from .simulators.batch_utils import RESULT_COVERAGE_KEY, RESULT_DROPOUT_FLAG_KEY


_HAS_PYFINITE = True  # compatibility with older tests


def _robust_soliton_cdf(k: int, c: float = 0.1, delta: float = 0.5) -> list[float]:
    """Return the cumulative distribution for the robust soliton.

    Parameters
    ----------
    k:
        Number of source symbols.
    c:
        Scaling factor controlling the expected ripple size.
    delta:
        Failure probability of the distribution.
    """
    if k <= 0:
        return [1.0]

    R = c * math.log(k / delta) * math.sqrt(k)
    m = int(k / R)
    if m <= 0:
        m = 1
    if m > k:
        m = k

    tau = [0.0] * (k + 1)
    for i in range(1, m):
        tau[i] = R / (i * k)
    tau[m] = R * math.log(R / delta) / k

    rho = [0.0] * (k + 1)
    rho[1] = 1.0 / k
    for i in range(2, k + 1):
        rho[i] = 1.0 / (i * (i - 1))

    dist = [rho[i] + tau[i] for i in range(1, k + 1)]
    total = sum(dist)
    return list(accumulate(d / total for d in dist))


def _sample_degree(cdf: list[float], rnd: random.Random) -> int:
    r = rnd.random()
    for idx, cutoff in enumerate(cdf, start=1):
        if r <= cutoff:
            return idx
    return len(cdf)


def _xor_into(target: bytearray, src: bytes | bytearray) -> None:
    for i, b in enumerate(src):
        target[i] ^= b


def _oligo_seed(oligo: SequenceOligo) -> int:
    if oligo.seed is not None:
        return int(oligo.seed)
    seed_token = oligo.metadata.get("droplet_seed") or oligo.metadata.get("seed")
    if seed_token is None:
        raise ValueError("Droplet missing seed metadata")
    return int(seed_token)


def _metadata_flag_true(metadata: Mapping[str, Any], key: str) -> bool:
    value = metadata.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        token = value.strip().lower()
        return token in {"1", "true", "yes", "y", "on"}
    return False


def _metadata_int(metadata: Mapping[str, Any], key: str) -> int | None:
    value = metadata.get(key)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _survivor_oligos(batch: SequenceBatch) -> list[SequenceOligo]:
    survivors: list[SequenceOligo] = []
    for oligo in batch.oligos:
        dropout_flag = _metadata_flag_true(oligo.metadata, RESULT_DROPOUT_FLAG_KEY)
        coverage_val = _metadata_int(oligo.metadata, RESULT_COVERAGE_KEY)
        if dropout_flag or (coverage_val is not None and coverage_val <= 0):
            continue
        survivors.append(oligo)
    return survivors


def _has_valid_seed(oligo: SequenceOligo) -> bool:
    try:
        _oligo_seed(oligo)
    except Exception:
        return False
    return True


def _batch_to_bytes(batch: SequenceBatch) -> bytes:
    """Return the packed droplet byte stream for ``batch``."""

    chunks: list[bytes] = []
    for oligo in batch.oligos:
        seed = _oligo_seed(oligo)
        payload_hex = oligo.sequence.strip()
        if len(payload_hex) % 2 != 0:
            raise ValueError("Droplet payload hex must contain an even number of symbols")
        payload = bytes.fromhex(payload_hex)
        chunks.append(seed.to_bytes(4, "big") + payload)
    return b"".join(chunks)


def droplet_batch_to_bytes(batch: SequenceBatch) -> bytes:
    """Expose the packed droplet stream for ``batch`` to external callers."""

    return _batch_to_bytes(batch)


def encode_data_fountain(
    data: bytes,
    chunk_size: int = 4,
    *,
    seed: int = 0,
    redundancy: float = 2.0,
    droplet_count: int | None = None,
    c: float = 0.1,
    delta: float = 0.5,
    manifest_path: str | Path | None = None,
) -> Tuple[SequenceBatch, Any]:
    """Encode ``data`` using an LT fountain scheme.

    The ``c`` and ``delta`` parameters control the robust soliton distribution
    used when selecting droplet degrees. They are forwarded directly to
    :func:`_robust_soliton_cdf`. Droplets are returned as a
    :class:`~genecoder.formats.SequenceBatch` where each oligo stores the
    droplet seed and payload metadata.

    Parameters
    ----------
    data:
        Bytes to encode.
    chunk_size:
        Size of each chunk used to create droplets.
    seed:
        Base seed for droplet generation.
    redundancy:
        Number of droplets to emit relative to ``k`` (the number of chunks).
        Ignored if ``droplet_count`` is provided.
    droplet_count:
        Explicit number of droplets to emit. If ``None`` the value is derived
        from ``redundancy``.
    c:
        Scaling factor controlling the expected ripple size of the robust
        soliton distribution.
    delta:
        Failure probability for the robust soliton distribution.
    manifest_path:
        Optional filesystem path where droplet metadata will be exported as a
        JSON manifest. When provided, parent directories are created
        automatically.
    """

    if not data:
        batch = SequenceBatch(
            batch_id="fountain",
            metadata={
                "batch_id": "fountain",
                "batch_size": "0",
                "chunk_size": str(chunk_size),
            },
            seed=seed,
            oligos=[],
        )
        info = {
            "chunk_size": chunk_size,
            "orig_len": 0,
            "k": 0,
            "seed": seed,
            "c": c,
            "delta": delta,
            "droplet_count": 0,
        }
        if manifest_path is not None:
            path = Path(manifest_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "chunk_size": chunk_size,
                        "orig_len": 0,
                        "seed": seed,
                        "c": c,
                        "delta": delta,
                        "droplets": [],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        return batch, info

    k = math.ceil(len(data) / chunk_size)
    blocks = [
        data[i : i + chunk_size].ljust(chunk_size, b"\x00")
        for i in range(0, len(data), chunk_size)
    ]
    num_droplets = (
        droplet_count
        if droplet_count is not None
        else max(k, int(math.ceil(k * redundancy)))
    )
    cdf = _robust_soliton_cdf(k, c=c, delta=delta)

    batch_id = f"fountain-{seed}"
    batch_metadata = {
        "batch_id": batch_id,
        "batch_size": str(num_droplets),
        "chunk_size": str(chunk_size),
        "k": str(k),
        "orig_len": str(len(data)),
        "seed": str(seed),
        "redundancy": f"{redundancy:.4f}",
    }

    oligos: list[SequenceOligo] = []
    manifest_entries: list[dict[str, Any]] = []
    for i in range(num_droplets):
        droplet_seed = seed + i
        rnd = random.Random(droplet_seed)
        if i < k:
            degree = 1
            indices = [i]
        else:
            degree = _sample_degree(cdf, rnd)
            indices = rnd.sample(range(k), degree)
        payload = bytearray(chunk_size)
        for idx in indices:
            _xor_into(payload, blocks[idx])
        payload_hex = bytes(payload).hex().upper()
        metadata = {
            "batch_id": batch_id,
            "batch_size": str(num_droplets),
            "oligo_index": str(i + 1),
            "oligo_id": f"{batch_id}-{i + 1:04d}",
            "droplet_seed": str(droplet_seed),
            "droplet_index": str(i),
            "payload_format": "hex",
            "chunk_size": str(chunk_size),
        }
        header = (
            f"batch_id={batch_id} oligo_index={i + 1} droplet_seed={droplet_seed} "
            f"payload_format=hex"
        )
        oligos.append(
            SequenceOligo(
                sequence=payload_hex,
                header=header,
                index=i + 1,
                oligo_id=metadata["oligo_id"],
                metadata=metadata,
                seed=droplet_seed,
            )
        )
        manifest_entries.append(
            {
                "index": i,
                "seed": droplet_seed,
                "degree": degree,
                "sources": indices,
            }
        )

    batch = SequenceBatch(
        batch_id=batch_id,
        metadata=batch_metadata,
        seed=seed,
        oligos=oligos,
    )

    if manifest_path is not None:
        path = Path(manifest_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        manifest_payload = {
            "chunk_size": chunk_size,
            "orig_len": len(data),
            "seed": seed,
            "c": c,
            "delta": delta,
            "k": k,
            "droplets": manifest_entries,
        }
        path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

    info = {
        "chunk_size": chunk_size,
        "orig_len": len(data),
        "k": k,
        "seed": seed,
        "c": c,
        "delta": delta,
        "droplet_count": num_droplets,
    }
    return batch, info


def decode_data_fountain(
    encoded: bytes | SequenceBatch,
    info: Mapping[str, Any],
    *,
    c: float | None = None,
    delta: float | None = None,
) -> Tuple[bytes, int]:
    """Decode bytes produced by :func:`encode_data_fountain`.

    Parameters
    ----------
    encoded:
        Bytes emitted by :func:`encode_data_fountain` or a
        :class:`~genecoder.formats.SequenceBatch` containing the surviving
        droplets.
    info:
        Mapping returned alongside the encoded data.
    c:
        Override for the robust soliton ``c`` parameter. If not provided, the
        value stored in ``info`` (or the default) is used. Forwarded to
        :func:`_robust_soliton_cdf`.
    delta:
        Override for the robust soliton ``delta`` parameter. If not provided,
        the value stored in ``info`` (or the default) is used. Forwarded to
        :func:`_robust_soliton_cdf`.

    Only droplets present in ``encoded`` are used during belief-propagation.
    """

    chunk_size = int(info["chunk_size"])
    orig_len = int(info["orig_len"])
    k = int(info.get("k", 0))
    if k == 0:
        return b"", 0

    c = float(info.get("c", 0.1)) if c is None else c
    delta = float(info.get("delta", 0.5)) if delta is None else delta

    base_seed = int(info.get("seed", 0))
    droplets: list[tuple[int, bytearray]] = []
    if isinstance(encoded, SequenceBatch):
        candidates = _survivor_oligos(encoded) or list(encoded.oligos)

        for oligo in candidates:
            seed_val = _oligo_seed(oligo)
            payload_hex = oligo.sequence.strip()
            if len(payload_hex) % 2 != 0:
                raise ValueError("Droplet payload hex must have even length")
            payload_bytes = bytes.fromhex(payload_hex)
            if len(payload_bytes) != chunk_size:
                if len(payload_bytes) < chunk_size:
                    payload_bytes = payload_bytes.ljust(chunk_size, b"\x00")
                else:
                    payload_bytes = payload_bytes[:chunk_size]
            droplets.append((seed_val, bytearray(payload_bytes)))
    else:
        droplet_size = chunk_size + 4
        for i in range(0, len(encoded), droplet_size):
            seed_val = int.from_bytes(encoded[i : i + 4], "big")
            payload = bytearray(encoded[i + 4 : i + droplet_size])
            droplets.append((seed_val, payload))

    cdf = _robust_soliton_cdf(k, c=c, delta=delta)
    ripple: deque[dict[str, Any]] = deque()
    equations: list[dict[str, Any]] = []
    for seed_val, payload in droplets:
        rnd = random.Random(seed_val)
        offset = seed_val - base_seed
        if 0 <= offset < k:
            degree = 1
            indices = [offset]
        else:
            degree = _sample_degree(cdf, rnd)
            indices = rnd.sample(range(k), degree)
        unknown = set(indices)
        equation = {"indices": indices, "payload": payload, "unknown": unknown}
        equations.append(equation)
        if len(unknown) == 1:
            ripple.append(equation)

    pieces: list[bytearray | None] = [None] * k

    while ripple:
        equation = ripple.popleft()
        if not equation["unknown"]:
            continue
        target_idx = next(iter(equation["unknown"]))
        payload = equation["payload"]
        if pieces[target_idx] is not None:
            continue
        pieces[target_idx] = bytearray(payload)
        equation["unknown"].clear()
        for other in equations:
            if target_idx not in other["unknown"]:
                continue
            other["unknown"].remove(target_idx)
            _xor_into(other["payload"], cast(bytearray, pieces[target_idx]))
            if len(other["unknown"]) == 1:
                ripple.append(other)

    if any(piece is None for piece in pieces):
        residual_rows: list[tuple[int, bytearray]] = []
        for equation in equations:
            if not equation["unknown"]:
                continue
            mask = 0
            for idx in equation["unknown"]:
                mask |= 1 << idx
            residual_rows.append((mask, bytearray(equation["payload"])))

        if residual_rows:
            rows = [list(row) for row in residual_rows]
            pivot_rows: dict[int, int] = {}
            row_idx = 0
            for col in range(k):
                pivot_row = None
                for r in range(row_idx, len(rows)):
                    if rows[r][0] & (1 << col):
                        pivot_row = r
                        break
                if pivot_row is None:
                    continue
                rows[row_idx], rows[pivot_row] = rows[pivot_row], rows[row_idx]
                pivot_mask, pivot_payload = rows[row_idx]
                for r in range(len(rows)):
                    if r != row_idx and (rows[r][0] & (1 << col)):
                        rows[r][0] ^= pivot_mask
                        _xor_into(rows[r][1], cast(bytearray, pivot_payload))
                pivot_rows[col] = row_idx
                row_idx += 1
                if row_idx == len(rows):
                    break

            for mask, payload in rows[row_idx:]:
                if mask == 0 and any(payload):
                    raise ValueError("Fountain decode failed")

            solved: dict[int, bytearray] = {}
            for col in sorted(pivot_rows.keys(), reverse=True):
                row_mask, row_payload = rows[pivot_rows[col]]
                payload = bytearray(row_payload)
                remaining = row_mask & ~(1 << col)
                unresolved = False
                while remaining:
                    idx = (remaining & -remaining).bit_length() - 1
                    if pieces[idx] is not None:
                        _xor_into(payload, cast(bytearray, pieces[idx]))
                    elif idx in solved:
                        _xor_into(payload, solved[idx])
                    else:
                        unresolved = True
                        break
                    remaining &= remaining - 1
                if not unresolved:
                    solved[col] = payload
            for idx, payload in solved.items():
                if pieces[idx] is None:
                    pieces[idx] = payload

    if any(piece is None for piece in pieces):
        raise ValueError("Fountain decode failed")

    data = b"".join(bytes(cast(bytearray, p)) for p in pieces)[:orig_len]
    return data, 0


class FountainFEC(FEC):
    """Simple Fountain code backend implementing :class:`BaseFEC`."""

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
        manifest_path: str | Path | None = None,
        **kwargs: Any,
    ) -> Tuple[bytes, Mapping[str, Any]]:  # noqa: ANN401
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
        return _batch_to_bytes(batch), info

    def decode(
        self,
        encoded: bytes,
        info: Mapping[str, Any],
        /,
        *,
        c: float | None = None,
        delta: float | None = None,
        survivor_batch: SequenceBatch | None = None,
        **kwargs: Any,
    ) -> Tuple[bytes, int]:  # noqa: ANN401
        source_batch = None
        if survivor_batch is not None:
            candidates = _survivor_oligos(survivor_batch) or list(survivor_batch.oligos)
            if candidates and all(_has_valid_seed(oligo) for oligo in candidates):
                source_batch = survivor_batch

        source: SequenceBatch | bytes = source_batch if source_batch is not None else encoded
        return decode_data_fountain(source, info, c=c, delta=delta)


from typing import Callable


def register(register_fec: Callable[[str, type[FEC]], None]) -> None:
    """Register this module's FEC backend."""
    register_fec("fountain", FountainFEC)

