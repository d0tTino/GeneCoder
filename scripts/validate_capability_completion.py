#!/usr/bin/env python3
"""Validate strategy capability completion criteria from test/benchmark artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "docs" / "strategy_model.yaml"



def _resolve(path: str, artifacts_dir: Path) -> Path:
    rel = Path(path)
    if rel.parts and rel.parts[0] == "artifacts":
        rel = Path(*rel.parts[1:])
    return artifacts_dir / rel


def _load_junit_cases(path: Path) -> dict[str, str]:
    tree = ET.parse(path)
    root = tree.getroot()
    cases: dict[str, str] = {}
    for case in root.iter("testcase"):
        classname = case.attrib.get("classname", "")
        name = case.attrib.get("name", "")
        case_id = f"{classname}::{name}"
        status = "passed"
        if case.find("failure") is not None or case.find("error") is not None:
            status = "failed"
        elif case.find("skipped") is not None:
            status = "skipped"
        cases[case_id] = status
    return cases


def _matches_where(item: dict, where: dict[str, object]) -> bool:
    for key, expected in where.items():
        if item.get(key) != expected:
            return False
    return True


def _evaluate_benchmark_aggregate(payload: dict, aggregate: dict) -> tuple[bool, str]:
    metric = aggregate["metric"]
    op = aggregate["op"]
    threshold = float(aggregate["threshold"])
    where = aggregate.get("where", {})
    values = [
        float(item[metric])
        for item in payload.get("results", [])
        if _matches_where(item, where)
    ]
    if not values:
        return False, f"no benchmark results matched filter {where} for metric {metric}"
    observed = min(values) if op == "min" else max(values)
    if op == "min":
        passed = observed >= threshold
        op_text = ">="
    elif op == "max":
        passed = observed <= threshold
        op_text = "<="
    else:
        return False, f"unsupported aggregate op {op!r}"
    return passed, f"{op}({metric})={observed:.6f} {op_text} {threshold:.6f}"


def validate(model: dict, artifacts_dir: Path) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for capability in model.get("feature_capabilities", []):
        if capability.get("status") != "implemented":
            continue
        criteria = capability.get("completion_criteria") or []
        if not criteria:
            failures.append(
                f"{capability['id']}: status=implemented but completion_criteria not defined"
            )
            continue

        for criterion in criteria:
            criterion_id = criterion.get("id", "<missing-id>")
            artifacts = criterion.get("artifacts") or []
            if not artifacts:
                failures.append(f"{capability['id']}::{criterion_id}: no artifacts listed")
                continue

            for artifact in artifacts:
                artifact_type = artifact.get("type")
                artifact_path = _resolve(str(artifact.get("path", "")), artifacts_dir)
                if not artifact_path.exists():
                    failures.append(
                        f"{capability['id']}::{criterion_id}: missing artifact {artifact_path}"
                    )
                    continue

                if artifact_type == "junit_xml":
                    checks = artifact.get("checks") or []
                    junit_cases = _load_junit_cases(artifact_path)
                    for case_id in checks:
                        status = junit_cases.get(case_id)
                        if status is None:
                            failures.append(
                                f"{capability['id']}::{criterion_id}: testcase not found {case_id} in {artifact_path}"
                            )
                        elif status != "passed":
                            failures.append(
                                f"{capability['id']}::{criterion_id}: testcase {case_id} status={status}"
                            )
                elif artifact_type == "benchmark_json":
                    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
                    expected_benchmark = artifact.get("benchmark")
                    if payload.get("benchmark") != expected_benchmark:
                        failures.append(
                            f"{capability['id']}::{criterion_id}: benchmark mismatch expected={expected_benchmark} got={payload.get('benchmark')}"
                        )
                        continue
                    passed, detail = _evaluate_benchmark_aggregate(payload, artifact["aggregate"])
                    if not passed:
                        failures.append(f"{capability['id']}::{criterion_id}: {detail}")
                else:
                    failures.append(
                        f"{capability['id']}::{criterion_id}: unsupported artifact type {artifact_type!r}"
                    )

    return not failures, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", type=Path, default=MODEL_PATH, help="Path to strategy model YAML"
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=ROOT / "artifacts",
        help="Directory containing evidence artifacts",
    )
    args = parser.parse_args()

    model = yaml.safe_load(args.model.read_text(encoding="utf-8"))
    passed, failures = validate(model, args.artifacts_dir)
    if not passed:
        print("Capability completion validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Capability completion validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
