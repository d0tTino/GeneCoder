#!/usr/bin/env python3
"""Validate benchmark gate thresholds against capability and roadmap docs."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS_PATH = ROOT / "configs" / "benchmark_thresholds.json"
CAPABILITIES_PATH = ROOT / "docs" / "capabilities.yaml"
ROADMAP_PATH = ROOT / "docs" / "development_roadmap.md"


def _load_thresholds() -> dict[str, dict[str, object]]:
    return json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))


def _extract_gate_block(text: str, gate: str) -> str:
    marker = f'- gate: "{gate}"'
    start = text.find(marker)
    if start == -1:
        raise ValueError(f"Missing gate {gate!r} in {CAPABILITIES_PATH}.")
    next_start = text.find('\n  - gate: "', start + len(marker))
    return text[start:] if next_start == -1 else text[start:next_start]


def _extract_metric_block(gate_block: str, metric: str) -> str:
    marker = f"- metric: {metric}"
    start = gate_block.find(marker)
    if start == -1:
        raise ValueError(f"Missing measurable check metric {metric!r} in capabilities gate block.")
    next_start = gate_block.find("\n      - metric:", start + len(marker))
    return gate_block[start:] if next_start == -1 else gate_block[start:next_start]


def _threshold_tokens(config_name: str) -> list[str]:
    return ["throughput", "BER"] if config_name == "throughput" else ["BER"]


def main() -> int:
    thresholds = _load_thresholds()
    capabilities_text = CAPABILITIES_PATH.read_text(encoding="utf-8")
    roadmap_text = ROADMAP_PATH.read_text(encoding="utf-8")

    failures: list[str] = []

    for benchmark_name, benchmark_cfg in thresholds.items():
        if "metric" not in benchmark_cfg or "benchmark_command" not in benchmark_cfg:
            continue
        gate = str(benchmark_cfg["gate"])
        metric = str(benchmark_cfg["metric"])
        benchmark_command = str(benchmark_cfg["benchmark_command"])

        gate_block = _extract_gate_block(capabilities_text, gate)
        metric_block = _extract_metric_block(gate_block, metric)

        for token in _threshold_tokens(benchmark_name):
            if token not in metric_block:
                failures.append(
                    f"{benchmark_name}: capabilities threshold mismatch. expected token {token!r}."
                )
            if token not in roadmap_text:
                failures.append(
                    f"{benchmark_name}: roadmap threshold mismatch. expected token {token!r}."
                )

        if benchmark_command not in metric_block:
            failures.append(
                f"{benchmark_name}: benchmark command {benchmark_command!r} missing from capabilities tests_or_checks."
            )
        if benchmark_command not in roadmap_text:
            failures.append(
                f"{benchmark_name}: benchmark command {benchmark_command!r} missing from roadmap."
            )

        for artifact in ["benchmark stdout artifact", "benchmark gate JSON artifact"]:
            if artifact not in metric_block:
                failures.append(
                    f"{benchmark_name}: capabilities evidence_artifacts missing {artifact!r}."
                )

    if failures:
        print("Benchmark gate alignment failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Benchmark gate alignment check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
