#!/usr/bin/env python3
"""Fail when roadmap references unsupported modules."""

from __future__ import annotations

from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "docs" / "strategy_model.yaml"


def _matches_any_prefix(value: str, prefixes: list[str]) -> str | None:
    for prefix in prefixes:
        if value.startswith(prefix):
            return prefix
    return None


def _check_model(model: dict) -> list[str]:
    policy = model.get("support_policy", {})
    unsupported_prefixes = policy.get("unsupported_module_prefixes", [])
    if not unsupported_prefixes:
        return []

    violations: list[str] = []

    for capability in model.get("feature_capabilities", []):
        capability_id = capability.get("id", "<unknown>")
        for owner in capability.get("owner_modules", []):
            prefix = _matches_any_prefix(owner, unsupported_prefixes)
            if prefix:
                violations.append(
                    f"feature_capabilities[{capability_id}].owner_modules includes unsupported path '{owner}' (prefix '{prefix}')"
                )

    for gate in model.get("kpi_gates", []):
        gate_name = gate.get("gate", "<unknown gate>")
        for check in gate.get("checks", []):
            metric = check.get("metric", "<unknown metric>")
            for evidence in check.get("evidence", []):
                prefix = _matches_any_prefix(evidence, unsupported_prefixes)
                if prefix:
                    violations.append(
                        f"kpi_gates[{gate_name} -> {metric}].evidence includes unsupported path '{evidence}' (prefix '{prefix}')"
                    )

    return violations


def main() -> int:
    model = yaml.safe_load(MODEL_PATH.read_text(encoding="utf-8"))
    violations = _check_model(model)
    if violations:
        print("Roadmap support policy violations detected:")
        for violation in violations:
            print(f" - {violation}")
        return 1
    print("Roadmap support policy check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
