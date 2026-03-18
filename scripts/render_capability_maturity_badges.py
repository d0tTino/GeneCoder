#!/usr/bin/env python3
"""Render capability maturity badges from strategy-derived capabilities metadata and CI job coverage."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES_PATH = ROOT / "docs" / "capabilities.yaml"
CI_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "python-ci.yml"
OUTPUT_PATH = ROOT / "docs" / "capability_maturity_badges.md"
GENERATED_HEADER = (
    "<!-- GENERATED FILE: derived from docs/strategy_model.yaml via docs/capabilities.yaml; "
    "edit docs/strategy_model.yaml and rerun "
    "`python scripts/generate_strategy_artifacts.py --write`. -->"
)


def _badge_url(label: str, message: str, color: str) -> str:
    safe_label = label.replace(" ", "%20")
    safe_message = message.replace(" ", "%20")
    return f"https://img.shields.io/badge/{safe_label}-{safe_message}-{color}"


def _maturity_message(status: str, ci_covered: bool) -> tuple[str, str]:
    if status == "implemented":
        return ("stable", "brightgreen") if ci_covered else ("stable-unchecked", "yellow")
    if status == "partial":
        return ("in-progress", "orange") if ci_covered else ("in-progress-unchecked", "red")
    return ("unknown", "lightgrey")


def render_markdown(capabilities_data: dict, workflow_data: dict) -> str:
    jobs = workflow_data.get("jobs", {})
    lines = [
        GENERATED_HEADER,
        "",
        "# Capability maturity badges",
        "",
        "Generated from `docs/strategy_model.yaml`, `docs/capabilities.yaml`, and `.github/workflows/python-ci.yml`.",
        "",
        "| Capability ID | Status | CI checks present | Maturity badge |",
        "| --- | --- | --- | --- |",
    ]

    for capability in capabilities_data.get("capabilities", []):
        ci_checks = capability.get("ci_status_checks", [])
        present = all(check in jobs for check in ci_checks) if ci_checks else False
        maturity_message, color = _maturity_message(str(capability.get("status", "unknown")), present)
        ci_badge = "yes" if present else "no"
        badge = _badge_url("capability maturity", maturity_message, color)
        lines.append(
            "| "
            f"`{capability['id']}` | `{capability['status']}` | `{ci_badge}` | "
            f"![{capability['id']} maturity]({badge}) |"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write badges file instead of checking")
    args = parser.parse_args()

    capabilities_data = yaml.safe_load(CAPABILITIES_PATH.read_text(encoding="utf-8"))
    workflow_data = yaml.safe_load(CI_WORKFLOW_PATH.read_text(encoding="utf-8"))
    rendered = render_markdown(capabilities_data, workflow_data)

    if args.write:
        OUTPUT_PATH.write_text(rendered, encoding="utf-8")
        print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)}")
        return 0

    existing = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
    if existing != rendered:
        print("Capability maturity badges are out of date. Run:")
        print("  python scripts/render_capability_maturity_badges.py --write")
        return 1

    print("Capability maturity badges are up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
