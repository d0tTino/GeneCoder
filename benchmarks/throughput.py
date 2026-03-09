from __future__ import annotations

import argparse
import json
import time
from typing import Any

from genecoder.encoders import decode_base4_direct, encode_base4_direct
from genecoder.gc_constrained_encoder import decode_gc_balanced, encode_gc_balanced
from genecoder.huffman_coding import decode_huffman, encode_huffman

from corpus_utils import corpus_sha256, load_frozen_bytes, load_profile_matrix


CodecResult = tuple[str, dict[str, Any]]


def _run_codec(codec: str, data: bytes) -> CodecResult:
    start = time.perf_counter()
    if codec == "base4":
        dna = encode_base4_direct(data)
        encode_time = time.perf_counter() - start
        start = time.perf_counter()
        decoded, _ = decode_base4_direct(dna)
        decode_time = time.perf_counter() - start
    elif codec == "huffman":
        dna, table, padding = encode_huffman(data)
        encode_time = time.perf_counter() - start
        start = time.perf_counter()
        decoded = decode_huffman(dna, table, padding)
        decode_time = time.perf_counter() - start
    elif codec == "gc_balanced":
        dna = encode_gc_balanced(data, 0.45, 0.55, 3)
        encode_time = time.perf_counter() - start
        start = time.perf_counter()
        decoded = decode_gc_balanced(dna)
        decode_time = time.perf_counter() - start
    else:
        raise ValueError(f"Unsupported codec profile: {codec}")

    size_mb = len(data) / (1024 * 1024)
    throughput = size_mb / (encode_time + decode_time) if (encode_time + decode_time) else 0.0
    return codec, {
        "throughput": throughput,
        "BER": 0.0,
        "decode_success": decoded == data,
        "runtime_per_mb": (encode_time + decode_time) / size_mb if size_mb else 0.0,
        "encode_mb_s": size_mb / encode_time if encode_time else 0.0,
        "decode_mb_s": size_mb / decode_time if decode_time else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reproducible throughput benchmarks")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    matrix = load_profile_matrix()
    results: list[dict[str, Any]] = []
    for profile in matrix["profiles"]:
        if profile["substitution_prob"] != 0.0:
            continue
        data = load_frozen_bytes(int(profile["bytes"]))
        _, metrics = _run_codec(str(profile["codec"]), data)
        results.append({"profile": profile["id"], "codec": profile["codec"], **metrics})

    payload = {
        "benchmark": "throughput",
        "corpus_version": matrix["version"],
        "corpus_sha256": corpus_sha256(),
        "results": results,
    }

    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        for item in results:
            print(
                f"{item['profile']:24} throughput={item['throughput']:.4f} MB/s "
                f"runtime_per_mb={item['runtime_per_mb']:.4f}s decode_success={item['decode_success']}"
            )


if __name__ == "__main__":
    main()
