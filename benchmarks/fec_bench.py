#!/usr/bin/env python
"""Benchmark forward error correction back-ends."""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import time
from pathlib import Path

from genecoder import FEC_REGISTRY, load_plugins

REDUNDANCY_ARGS = {
    "bch": "t",
    "reed_solomon": "nsym",
    "fountain": "chunk_size",
    "raptorq": "symbol_size",
}


DATA_SIZE = 1_000_000  # 1 MB of random bytes
ERROR_PROB = 0.01  # probability of flipping each bit


def bit_error_rate(original: bytes, recovered: bytes) -> float:
    """Return the bit error rate between two byte strings."""
    total_bits = len(original) * 8
    min_len = min(len(original), len(recovered))
    errors = 0
    for o, r in zip(original[:min_len], recovered[:min_len]):
        errors += (o ^ r).bit_count()
    if len(recovered) < len(original):
        errors += (len(original) - len(recovered)) * 8
    return errors / total_bits if total_bits else 0.0


def introduce_bit_errors(data: bytes, prob: float, rng: random.Random | None = None) -> bytes:
    """Flip bits in ``data`` with probability ``prob``."""
    rng = rng or random.Random()
    arr = bytearray(data)
    for i in range(len(arr)):
        for b in range(8):
            if rng.random() < prob:
                arr[i] ^= 1 << b
    return bytes(arr)


def bench_backend(
    name: str,
    encode,
    decode,
    data: bytes,
    prob: float,
    redundancy: int | None = None,
    param: str | None = None,
) -> dict[str, float | str]:
    start = time.perf_counter()
    try:
        if redundancy is not None and param:
            encoded, info = encode(data, **{param: redundancy})
        elif redundancy is not None:
            encoded, info = encode(data, redundancy)
        else:
            encoded, info = encode(data)
    except Exception as exc:  # pragma: no cover - optional deps
        return {"fec": name, "error": str(exc)}
    enc_time = time.perf_counter() - start

    noisy = introduce_bit_errors(encoded, prob)
    start = time.perf_counter()
    try:
        decoded, _ = decode(noisy, info)
    except Exception as exc:  # pragma: no cover - error path
        return {
            "fec": name,
            "encode_mb_s": len(data) / (1024 * 1024) / enc_time,
            "error": str(exc),
        }
    dec_time = time.perf_counter() - start
    ber = bit_error_rate(data, decoded)
    redundancy_ratio = len(encoded) / len(data) if len(data) else 0.0
    return {
        "fec": name,
        "redundancy": redundancy_ratio,
        "encode_mb_s": len(data) / (1024 * 1024) / enc_time,
        "decode_mb_s": len(data) / (1024 * 1024) / dec_time,
        "ber": ber,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark FEC back-ends")
    parser.add_argument("--format", choices=["csv", "json"], default="csv")
    parser.add_argument("--output", "-o", type=Path, help="Write results to file")
    parser.add_argument("--size", type=int, default=DATA_SIZE, help="Data size in bytes")
    parser.add_argument(
        "--error-prob",
        type=float,
        default=ERROR_PROB,
        help="Bit flip probability",
    )
    parser.add_argument(
        "--redundancy",
        type=int,
        action="append",
        default=[0],
        help="Redundancy levels to test",
    )
    args = parser.parse_args()

    load_plugins()
    data = os.urandom(args.size)

    results: list[dict[str, float | str]] = []
    for name in sorted(FEC_REGISTRY):
        funcs = FEC_REGISTRY[name]
        param = REDUNDANCY_ARGS.get(name)
        for r in args.redundancy:
            result = bench_backend(
                name,
                funcs["encode"],
                funcs["decode"],
                data,
                args.error_prob,
                r,
                param,
            )
            result["redundancy_param"] = r
            results.append(result)

    out = open(args.output, "w", newline="") if args.output else sys.stdout
    if args.format == "csv":
        fieldnames = [
            "fec",
            "redundancy_param",
            "redundancy",
            "encode_mb_s",
            "decode_mb_s",
            "ber",
            "error",
        ]
        writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    else:
        json.dump(results, out, indent=2)
        if out is not sys.stdout:
            out.write("\n")
    if out is not sys.stdout:
        out.close()


if __name__ == "__main__":
    main()
