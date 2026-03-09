from __future__ import annotations

import argparse
import json
import time
from typing import Any

from genecoder.encoders import decode_base4_direct, encode_base4_direct

from corpus_utils import (
    corpus_sha256,
    load_frozen_bytes,
    load_profile_matrix,
    substitute_dna_bases,
)


def bit_error_rate(original: bytes, recovered: bytes) -> float:
    total_bits = len(original) * 8
    min_len = min(len(original), len(recovered))
    errors = 0
    for original_byte, recovered_byte in zip(original[:min_len], recovered[:min_len]):
        errors += (original_byte ^ recovered_byte).bit_count()
    if len(recovered) < len(original):
        errors += (len(original) - len(recovered)) * 8
    return errors / total_bits if total_bits else 0.0


def _run_profile(profile: dict[str, Any]) -> dict[str, Any]:
    data = load_frozen_bytes(int(profile["bytes"]))
    start = time.perf_counter()
    dna = encode_base4_direct(data)
    encode_time = time.perf_counter() - start

    noisy = substitute_dna_bases(dna, float(profile["substitution_prob"]), int(profile["seed"]))

    start = time.perf_counter()
    decoded, _ = decode_base4_direct(noisy)
    decode_time = time.perf_counter() - start

    size_mb = len(data) / (1024 * 1024)
    return {
        "profile": profile["id"],
        "codec": profile["codec"],
        "throughput": size_mb / (encode_time + decode_time) if (encode_time + decode_time) else 0.0,
        "BER": bit_error_rate(data, decoded),
        "decode_success": decoded == data,
        "runtime_per_mb": (encode_time + decode_time) / size_mb if size_mb else 0.0,
        "encode_mb_s": size_mb / encode_time if encode_time else 0.0,
        "decode_mb_s": size_mb / decode_time if decode_time else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reproducible BER benchmarks")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    matrix = load_profile_matrix()
    results = [_run_profile(p) for p in matrix["profiles"] if p["codec"] == "base4"]

    payload = {
        "benchmark": "error_rate",
        "corpus_version": matrix["version"],
        "corpus_sha256": corpus_sha256(),
        "results": results,
    }

    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        for item in results:
            print(
                f"{item['profile']:24} throughput={item['throughput']:.4f} MB/s BER={item['BER']:.6f} "
                f"runtime_per_mb={item['runtime_per_mb']:.4f}s decode_success={item['decode_success']}"
            )


if __name__ == "__main__":
    main()
