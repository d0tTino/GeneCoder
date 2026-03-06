#!/usr/bin/env python3
"""Evaluate benchmark outputs against roadmap capability gate thresholds."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

BENCHMARK_THRESHOLDS_PATH = Path("configs/benchmark_thresholds.json")
THROUGHPUT_PATTERN = re.compile(
    r"^Base-4\s+encode:\s+(?P<encode>[0-9.]+)\s+MB/s\s+decode:\s+(?P<decode>[0-9.]+)\s+MB/s$"
)
ERROR_RATE_PATTERN = re.compile(
    r"^encode:\s+(?P<encode>[0-9.]+)\s+MB/s\s+decode:\s+(?P<decode>[0-9.]+)\s+MB/s\s+BER:\s+(?P<ber>[0-9.]+)$"
)


def _load_threshold_config() -> dict[str, object]:
    with BENCHMARK_THRESHOLDS_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _parse_throughput(stdout_text: str) -> dict[str, float]:
    for line in stdout_text.splitlines():
        match = THROUGHPUT_PATTERN.match(line.strip())
        if match:
            return {
                "base4_encode_mb_s": float(match.group("encode")),
                "base4_decode_mb_s": float(match.group("decode")),
            }
    raise ValueError("Could not parse Base-4 throughput output from benchmark stdout.")


def _parse_error_rate(stdout_text: str) -> dict[str, float]:
    for line in stdout_text.splitlines():
        match = ERROR_RATE_PATTERN.match(line.strip())
        if match:
            return {
                "encode_mb_s": float(match.group("encode")),
                "decode_mb_s": float(match.group("decode")),
                "ber": float(match.group("ber")),
            }
    raise ValueError("Could not parse BER output from benchmark stdout.")


def _parsed_from_artifact(benchmark: str, artifact_data: dict[str, object]) -> dict[str, float]:
    parsed_metrics = artifact_data.get("parsed_metrics")
    if not isinstance(parsed_metrics, dict):
        raise ValueError("Artifact payload missing 'parsed_metrics' object.")

    if benchmark == "throughput":
        encode = parsed_metrics.get("base4_encode_mb_s")
        decode = parsed_metrics.get("base4_decode_mb_s")
        if not isinstance(encode, (int, float)) or not isinstance(decode, (int, float)):
            raise ValueError("Throughput artifact must contain numeric base4_encode_mb_s/base4_decode_mb_s.")
        return {"base4_encode_mb_s": float(encode), "base4_decode_mb_s": float(decode)}

    encode = parsed_metrics.get("encode_mb_s")
    decode = parsed_metrics.get("decode_mb_s")
    ber = parsed_metrics.get("ber")
    if not isinstance(encode, (int, float)) or not isinstance(decode, (int, float)) or not isinstance(ber, (int, float)):
        raise ValueError("Error-rate artifact must contain numeric encode_mb_s/decode_mb_s/ber.")
    return {"encode_mb_s": float(encode), "decode_mb_s": float(decode), "ber": float(ber)}


def _evaluate(benchmark: str, parsed: dict[str, float], config: dict[str, object]) -> tuple[bool, list[str]]:
    thresholds = config["thresholds"]
    checks: list[str] = []

    if benchmark == "throughput":
        minimum = float(thresholds["base4_encode_mb_s_min"])
        measured = parsed["base4_encode_mb_s"]
        checks.append(f"base4_encode_mb_s >= {minimum:.2f} (actual {measured:.2f})")
        return measured >= minimum, checks

    maximum = float(thresholds["ber_max"])
    measured = parsed["ber"]
    checks.append(f"ber <= {maximum:.5f} (actual {measured:.6f})")
    return measured <= maximum, checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark",
        required=True,
        choices=["throughput", "error_rate"],
        help="Benchmark profile name to evaluate.",
    )
    parser.add_argument(
        "--stdout-file",
        type=Path,
        help="Path to benchmark stdout file.",
    )
    parser.add_argument(
        "--artifact-json",
        type=Path,
        help="Path to benchmark artifact JSON containing parsed_metrics.",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        type=Path,
        help="Path to write machine-readable gate evaluation report.",
    )
    args = parser.parse_args()

    threshold_config = _load_threshold_config()
    benchmark_config = threshold_config[args.benchmark]

    if args.artifact_json:
        artifact_payload = json.loads(args.artifact_json.read_text(encoding="utf-8"))
        parsed = _parsed_from_artifact(args.benchmark, artifact_payload)
        evidence = str(args.artifact_json)
    else:
        if not args.stdout_file:
            raise SystemExit("Either --stdout-file or --artifact-json is required.")
        stdout_text = args.stdout_file.read_text(encoding="utf-8")
        parsed = (
            _parse_throughput(stdout_text)
            if args.benchmark == "throughput"
            else _parse_error_rate(stdout_text)
        )
        evidence = str(args.stdout_file)

    passed, checks = _evaluate(args.benchmark, parsed, benchmark_config)

    report = {
        "benchmark": args.benchmark,
        "gate": benchmark_config["gate"],
        "metric": benchmark_config["metric"],
        "benchmark_command": benchmark_config["benchmark_command"],
        "references": benchmark_config["references"],
        "thresholds": benchmark_config["thresholds"],
        "parsed_metrics": parsed,
        "checks": checks,
        "evidence_artifact": evidence,
        "passed": passed,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
