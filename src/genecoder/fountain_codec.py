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

import math
import random
from itertools import accumulate


_HAS_PYFINITE = True  # compatibility with older tests


def _robust_soliton_cdf(k: int, c: float = 0.1, delta: float = 0.5) -> list[float]:
    """Return the cumulative distribution for the robust soliton."""
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


def encode_data_fountain(
    data: bytes, chunk_size: int = 4, *, seed: int = 0, redundancy: float = 2.0
) -> Tuple[bytes, Any]:
    """Encode ``data`` using an LT fountain scheme.

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
    """

    if not data:
        return b"", {"chunk_size": chunk_size, "orig_len": 0, "k": 0}

    k = math.ceil(len(data) / chunk_size)
    blocks = [
        data[i : i + chunk_size].ljust(chunk_size, b"\x00")
        for i in range(0, len(data), chunk_size)
    ]
    num_droplets = max(k, int(k * redundancy))
    cdf = _robust_soliton_cdf(k)
    droplets: list[bytes] = []
    for i in range(num_droplets):
        droplet_seed = seed + i
        rnd = random.Random(droplet_seed)
        degree = _sample_degree(cdf, rnd)
        indices = rnd.sample(range(k), degree)
        payload = bytearray(chunk_size)
        for idx in indices:
            _xor_into(payload, blocks[idx])
        droplets.append(droplet_seed.to_bytes(4, "big") + bytes(payload))

    encoded = b"".join(droplets)
    info = {
        "chunk_size": chunk_size,
        "orig_len": len(data),
        "k": k,
        "seed": seed,
    }
    return encoded, info


def decode_data_fountain(encoded: bytes, info: Mapping[str, int]) -> Tuple[bytes, int]:
    """Decode bytes produced by :func:`encode_data_fountain`."""

    chunk_size = int(info["chunk_size"])
    orig_len = int(info["orig_len"])
    k = int(info.get("k", 0))
    if k == 0:
        return b"", 0

    droplet_size = chunk_size + 4
    droplets = [
        (
            int.from_bytes(encoded[i : i + 4], "big"),
            bytearray(encoded[i + 4 : i + droplet_size]),
        )
        for i in range(0, len(encoded), droplet_size)
    ]

    cdf = _robust_soliton_cdf(k)
    equations: list[tuple[list[int], bytearray]] = []
    for seed, payload in droplets:
        rnd = random.Random(seed)
        degree = _sample_degree(cdf, rnd)
        indices = rnd.sample(range(k), degree)
        equations.append((indices, payload))

    pieces: list[bytearray | None] = [None] * k

    progress = True
    while progress and equations:
        progress = False
        remaining: list[tuple[list[int], bytearray]] = []
        for indices, payload in equations:
            unknown = [i for i in indices if pieces[i] is None]
            if len(unknown) == 0:
                continue
            if len(unknown) == 1:
                j = unknown[0]
                for idx in indices:
                    if idx != j and pieces[idx] is not None:
                        _xor_into(payload, cast(bytearray, pieces[idx]))
                pieces[j] = payload
                progress = True
            else:
                remaining.append((indices, payload))
        equations = remaining

    if any(p is None for p in pieces):
        raise ValueError("Fountain decode failed")

    data = b"".join(cast(bytearray, p) for p in pieces)[:orig_len]
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
        **kwargs: Any,
    ) -> Tuple[bytes, Mapping[str, int]]:  # noqa: ANN401
        return encode_data_fountain(data, chunk_size, seed=seed, redundancy=redundancy)

    def decode(
        self, encoded: bytes, info: Mapping[str, int], /, **kwargs: Any
    ) -> Tuple[bytes, int]:  # noqa: ANN401
        return decode_data_fountain(encoded, info)


from typing import Callable


def register(register_fec: Callable[[str, type[FEC]], None]) -> None:
    """Register this module's FEC backend."""
    register_fec("fountain", FountainFEC)

