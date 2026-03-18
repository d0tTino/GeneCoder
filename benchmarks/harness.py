from __future__ import annotations

import json
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genecoder.encoders import decode_base4_direct, encode_base4_direct
from genecoder.gc_constrained_encoder import decode_gc_balanced, encode_gc_balanced
from genecoder.huffman_coding import decode_huffman, encode_huffman

from benchmarks.corpus_utils import corpus_sha256, load_frozen_bytes, substitute_dna_bases

MATRIX_PATH = Path(__file__).resolve().parents[1] / "configs" / "benchmark_matrix.yaml"
SCHEMA_VERSION = "1.0.0"
MUTATION_PARAMETER_KEYS = ("substitution_prob", "insertion_prob", "deletion_prob", "dropout_prob")


def _mutation_parameters(scenario: dict[str, Any]) -> dict[str, float]:
    return {key: float(scenario.get(key, 0.0)) for key in MUTATION_PARAMETER_KEYS}


def _normalize_scenario(scenario: dict[str, Any], profile_defaults: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(scenario)
    for key in MUTATION_PARAMETER_KEYS:
        if key not in normalized and key in profile_defaults:
            normalized[key] = profile_defaults[key]
    for key in MUTATION_PARAMETER_KEYS:
        normalized.setdefault(key, 0.0)
    return normalized


def _validated_scenarios(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    profiles = matrix.get("profiles", {})
    scenarios = matrix.get("scenarios", [])
    validated: list[dict[str, Any]] = []

    for index, raw_scenario in enumerate(scenarios):
        profile = str(raw_scenario.get("profile", ""))
        defaults = profiles.get(profile, {})
        scenario = _normalize_scenario(raw_scenario, defaults)
        mutation_params = _mutation_parameters(scenario)
        if profile == "noisy" and all(value == 0.0 for value in mutation_params.values()):
            raise ValueError(
                "Invalid benchmark scenario at index "
                f"{index}: profile=noisy requires at least one non-zero mutation parameter"
            )
        validated.append(scenario)

    return validated


def load_benchmark_matrix() -> dict[str, Any]:
    matrix = yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8"))
    matrix["scenarios"] = _validated_scenarios(matrix)
    return matrix


def bit_error_rate(original: bytes, recovered: bytes) -> float:
    total_bits = len(original) * 8
    min_len = min(len(original), len(recovered))
    errors = 0
    for original_byte, recovered_byte in zip(original[:min_len], recovered[:min_len]):
        errors += (original_byte ^ recovered_byte).bit_count()
    if len(recovered) < len(original):
        errors += (len(original) - len(recovered)) * 8
    return errors / total_bits if total_bits else 0.0


def _apply_simulator(dna: str, simulator: str, substitution_prob: float, seed: int) -> str:
    if simulator == "identity":
        return dna
    if simulator == "substitution":
        return substitute_dna_bases(dna, substitution_prob, seed)
    raise ValueError(f"Unsupported simulator: {simulator}")


def _encode_decode(codec: str, data: bytes, simulator: str, substitution_prob: float, seed: int) -> tuple[bytes, float, float]:
    start = time.perf_counter()
    if codec == "base4":
        dna = encode_base4_direct(data)
        encode_time = time.perf_counter() - start
        noisy_dna = _apply_simulator(dna, simulator, substitution_prob, seed)
        start = time.perf_counter()
        decoded, _ = decode_base4_direct(noisy_dna)
        decode_time = time.perf_counter() - start
        return decoded, encode_time, decode_time

    if substitution_prob > 0.0 and simulator != "identity":
        raise ValueError(f"Codec {codec} does not support noisy simulation in benchmark harness")

    if codec == "huffman":
        dna, table, padding = encode_huffman(data)
        encode_time = time.perf_counter() - start
        start = time.perf_counter()
        decoded, _ = decode_huffman(dna, table, padding)
        decode_time = time.perf_counter() - start
        return decoded, encode_time, decode_time
    if codec == "gc_balanced":
        dna = encode_gc_balanced(data, 0.45, 0.55, 3)
        encode_time = time.perf_counter() - start
        start = time.perf_counter()
        decoded = decode_gc_balanced(dna)
        decode_time = time.perf_counter() - start
        decoded_bytes = decoded[0] if isinstance(decoded, tuple) else decoded
        return decoded_bytes, encode_time, decode_time
    raise ValueError(f"Unsupported codec: {codec}")


def _scenario_id(codec: str, simulator: str, profile: str, payload_size: int, seed: int) -> str:
    size_kb = payload_size // 1024
    return f"{codec}_{simulator}_{profile}_{size_kb}kb_seed{seed}"


def _result_from_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    payload_size = int(scenario["payload_size"])
    data = load_frozen_bytes(payload_size)
    decoded, encode_time, decode_time = _encode_decode(
        codec=str(scenario["codec"]),
        data=data,
        simulator=str(scenario["simulator"]),
        substitution_prob=float(scenario["substitution_prob"]),
        seed=int(scenario["seed"]),
    )
    size_mb = len(data) / (1024 * 1024)
    total_runtime = encode_time + decode_time
    throughput = size_mb / total_runtime if total_runtime else 0.0

    return {
        "profile": _scenario_id(
            str(scenario["codec"]),
            str(scenario["simulator"]),
            str(scenario["profile"]),
            payload_size,
            int(scenario["seed"]),
        ),
        "codec": str(scenario["codec"]),
        "simulator": str(scenario["simulator"]),
        "profile_descriptor": str(scenario["profile"]),
        "payload_size": payload_size,
        "seed": int(scenario["seed"]),
        "substitution_prob": float(scenario["substitution_prob"]),
        "insertion_prob": float(scenario.get("insertion_prob", 0.0)),
        "deletion_prob": float(scenario.get("deletion_prob", 0.0)),
        "dropout_prob": float(scenario.get("dropout_prob", 0.0)),
        "throughput": throughput,
        "BER": bit_error_rate(data, decoded),
        "decode_success": decoded == data,
        "runtime_per_mb": total_runtime / size_mb if size_mb else 0.0,
        "encode_mb_s": size_mb / encode_time if encode_time else 0.0,
        "decode_mb_s": size_mb / decode_time if decode_time else 0.0,
    }


def _scenario_matches(benchmark: str, scenario: dict[str, Any]) -> bool:
    noisy = any(value > 0.0 for value in _mutation_parameters(scenario).values()) and str(scenario["simulator"]) != "identity"
    if benchmark == "throughput":
        return not noisy
    if benchmark == "error_rate":
        return str(scenario["codec"]) == "base4"
    raise ValueError(f"Unsupported benchmark: {benchmark}")


def iter_benchmark_results(benchmark: str, matrix: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for scenario in matrix.get("scenarios", []):
        if _scenario_matches(benchmark, scenario):
            yield _result_from_scenario(scenario)


def benchmark_payload(benchmark: str) -> dict[str, Any]:
    matrix = load_benchmark_matrix()
    results = sorted(iter_benchmark_results(benchmark, matrix), key=lambda item: item["profile"])
    return {
        "benchmark": benchmark,
        "schema_version": SCHEMA_VERSION,
        "matrix_version": str(matrix["version"]),
        "corpus_sha256": corpus_sha256(),
        "results": results,
    }


def render_payload(payload: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(payload, indent=2, sort_keys=True)
    lines = []
    for item in payload["results"]:
        lines.append(
            f"{item['profile']:48} throughput={item['throughput']:.4f} MB/s "
            f"BER={item['BER']:.6f} runtime_per_mb={item['runtime_per_mb']:.4f}s "
            f"decode_success={item['decode_success']}"
        )
    return "\n".join(lines)
