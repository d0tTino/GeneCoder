#!/usr/bin/env python3
"""Evaluate benchmark outputs against roadmap capability gate thresholds."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

BENCHMARK_THRESHOLDS_PATH = Path("configs/benchmark_thresholds.json")
THROUGHPUT_PATTERN = re.compile(
    r"^Base-4\s+encode:\s+(?P<encode>[0-9.]+)\s+MB/s\s+decode:\s+(?P<decode>[0-9.]+)\s+MB/s$"
)
ERROR_RATE_PATTERN = re.compile(
    r"^encode:\s+(?P<encode>[0-9.]+)\s+MB/s\s+decode:\s+(?P<decode>[0-9.]+)\s+MB/s\s+BER:\s+(?P<ber>[0-9.]+)$"
)


def _load_threshold_config() -> dict[str, Any]:
    with BENCHMARK_THRESHOLDS_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _parse_stdout(benchmark: str, stdout_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout_text)
        if isinstance(payload, dict) and isinstance(payload.get("results"), list):
            if "schema_version" in payload and "matrix_version" in payload:
                return payload
            return {"results": payload["results"]}
    except json.JSONDecodeError:
        pass

    if benchmark == "throughput":
        for line in stdout_text.splitlines():
            match = THROUGHPUT_PATTERN.match(line.strip())
            if match:
                return {
                    "results": [
                        {
                            "profile": "base4_legacy",
                            "throughput": float(match.group("encode")),
                            "BER": 0.0,
                            "decode_success": True,
                            "runtime_per_mb": 0.0,
                            "decode_mb_s": float(match.group("decode")),
                        }
                    ]
                }
        raise ValueError("Could not parse throughput output from benchmark stdout.")

    for line in stdout_text.splitlines():
        match = ERROR_RATE_PATTERN.match(line.strip())
        if match:
            return {
                "results": [
                    {
                        "profile": "error_rate_legacy",
                        "throughput": float(match.group("encode")),
                        "BER": float(match.group("ber")),
                        "decode_success": True,
                        "runtime_per_mb": 0.0,
                        "decode_mb_s": float(match.group("decode")),
                    }
                ]
            }
    raise ValueError("Could not parse BER output from benchmark stdout.")


def _parsed_from_artifact(artifact_data: dict[str, Any]) -> dict[str, Any]:
    parsed_metrics = artifact_data.get("parsed_metrics")
    if isinstance(parsed_metrics, dict) and isinstance(parsed_metrics.get("results"), list):
        if "schema_version" in parsed_metrics and "matrix_version" in parsed_metrics:
            return parsed_metrics
        return {"results": parsed_metrics["results"]}
    if isinstance(parsed_metrics, dict):
        return {"results": [parsed_metrics]}
    if isinstance(artifact_data.get("results"), list):
        return {"results": artifact_data["results"]}
    raise ValueError("Artifact payload missing benchmark results.")


def _evaluate(benchmark: str, parsed: dict[str, Any], config: dict[str, Any]) -> tuple[bool, list[str]]:
    baselines = config.get("baseline_snapshot", {})
    tolerances = config.get("tolerance_gates", {})
    checks: list[str] = []
    passed = True

    for result in parsed["results"]:
        profile = str(result.get("profile", "unknown"))
        baseline = baselines.get(profile)
        if not baseline:
            checks.append(f"{profile}: no baseline snapshot configured; skipped")
            continue

        throughput = float(result.get("throughput", 0.0))
        ber = float(result.get("BER", 1.0))
        decode_success = bool(result.get("decode_success", False))
        runtime_per_mb = float(result.get("runtime_per_mb", 0.0))

        min_tp = float(baseline["throughput"]) * (1 - float(tolerances.get("throughput_regression_pct", 0.0)))
        max_ber = float(baseline["BER"]) + float(tolerances.get("ber_absolute_delta", 0.0))
        max_runtime = float(baseline["runtime_per_mb"]) * (1 + float(tolerances.get("runtime_per_mb_regression_pct", 0.0)))

        profile_ok = (
            throughput >= min_tp
            and ber <= max_ber
            and runtime_per_mb <= max_runtime
            and (not bool(tolerances.get("require_decode_success", True)) or decode_success)
        )
        passed = passed and profile_ok

        checks.append(
            f"{profile}: throughput>={min_tp:.4f} actual={throughput:.4f}; "
            f"BER<={max_ber:.6f} actual={ber:.6f}; "
            f"runtime_per_mb<={max_runtime:.4f} actual={runtime_per_mb:.4f}; "
            f"decode_success={decode_success}"
        )

    return passed, checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True, choices=["throughput", "error_rate"])
    parser.add_argument("--stdout-file", type=Path)
    parser.add_argument("--artifact-json", type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    args = parser.parse_args()

    threshold_config = _load_threshold_config()
    benchmark_config = threshold_config[args.benchmark]

    if args.artifact_json:
        artifact_payload = json.loads(args.artifact_json.read_text(encoding="utf-8"))
        parsed = _parsed_from_artifact(artifact_payload)
        evidence = str(args.artifact_json)
    else:
        if not args.stdout_file:
            raise SystemExit("Either --stdout-file or --artifact-json is required.")
        parsed = _parse_stdout(args.benchmark, args.stdout_file.read_text(encoding="utf-8"))
        evidence = str(args.stdout_file)

    passed, checks = _evaluate(args.benchmark, parsed, benchmark_config)

    report = {
        "benchmark": args.benchmark,
        "gate": benchmark_config["gate"],
        "metric": benchmark_config["metric"],
        "benchmark_command": benchmark_config["benchmark_command"],
        "references": benchmark_config["references"],
        "baseline_snapshot": benchmark_config.get("baseline_snapshot", {}),
        "tolerance_gates": benchmark_config.get("tolerance_gates", {}),
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
