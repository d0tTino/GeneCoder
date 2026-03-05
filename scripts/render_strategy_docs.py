#!/usr/bin/env python3
"""Render strategy markdown docs from docs/strategy_model.yaml."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "docs" / "strategy_model.yaml"

OUTPUT_DOCS = {
    "product_strategy": ROOT / "docs" / "product_strategy.md",
    "development_roadmap": ROOT / "docs" / "development_roadmap.md",
    "roadmap_execution": ROOT / "docs" / "roadmap_execution.md",
    "cloud": ROOT / "docs" / "cloud.md",
    "cloud_worker": ROOT / "docs" / "cloud_worker.md",
}


def _format_checks(checks: list[dict]) -> str:
    lines = [
        "| Metric | Threshold | Evidence |",
        "| --- | --- | --- |",
    ]
    for check in checks:
        evidence = ", ".join(f"`{item}`" for item in check.get("evidence", [])) or "_None listed_"
        lines.append(f"| {check['metric']} | {check['threshold']} | {evidence} |")
    return "\n".join(lines)


def _render_capability_table(capabilities: list[dict]) -> str:
    lines = [
        "| Capability | Status | Phase | Owner modules |",
        "| --- | --- | --- | --- |",
    ]
    for capability in capabilities:
        owners = "<br>".join(f"`{path}`" for path in capability.get("owner_modules", [])) or "_Unspecified_"
        lines.append(
            f"| {capability['name']} | `{capability['status']}` | {capability['phase']} | {owners} |"
        )
    return "\n".join(lines)


def _render_product_strategy(model: dict) -> str:
    capabilities = model["feature_capabilities"]
    return "\n".join(
        [
            "# Product Strategy",
            "",
            f"> last_validated_commit: `{model['last_validated_commit']}`",
            "",
            "## Phase definitions",
            "",
            "| Phase | Name | Objective |",
            "| --- | --- | --- |",
            *[
                f"| {phase['id']} | {phase['name']} | {phase['objective']} |"
                for phase in model["phases"]
            ],
            "",
            "## Feature capability statuses",
            "",
            _render_capability_table(capabilities),
            "",
            "## Deployment posture flags",
            "",
            "| Flag | Value |",
            "| --- | --- |",
            *[
                f"| `{flag}` | `{value}` |"
                for flag, value in model["deployment_posture"].items()
            ],
        ]
    ) + "\n"


def _render_development_roadmap(model: dict) -> str:
    blocks = [
        "# Development Roadmap",
        "",
        f"> last_validated_commit: `{model['last_validated_commit']}`",
        "",
    ]
    for gate in model["kpi_gates"]:
        blocks.extend([f"## {gate['gate']}", "", _format_checks(gate["checks"]), ""])
    return "\n".join(blocks).rstrip() + "\n"


def _render_roadmap_execution(model: dict) -> str:
    lines = [
        "# Roadmap Execution",
        "",
        f"> last_validated_commit: `{model['last_validated_commit']}`",
        "",
        "## Execution summary",
        "",
    ]
    for phase in model["phases"]:
        lines.append(f"- **Phase {phase['id']} — {phase['name']}**: {phase['execution_focus']}")
    lines.extend(["", "## KPI gate checklist", ""])
    for gate in model["kpi_gates"]:
        lines.append(f"### {gate['gate']}")
        for check in gate["checks"]:
            lines.append(f"- {check['metric']}: **{check['threshold']}**")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_cloud_doc(model: dict) -> str:
    posture = model["deployment_posture"]
    return "\n".join(
        [
            "# Cloud Status",
            "",
            f"> last_validated_commit: `{model['last_validated_commit']}`",
            "",
            "## Deployment posture",
            "",
            f"- `cloud_enabled`: `{posture['cloud_enabled']}`",
            f"- `cloud_worker_enabled`: `{posture['cloud_worker_enabled']}`",
            f"- `local_execution_only`: `{posture['local_execution_only']}`",
        ]
    ) + "\n"


def render_docs(model: dict) -> dict[Path, str]:
    return {
        OUTPUT_DOCS["product_strategy"]: _render_product_strategy(model),
        OUTPUT_DOCS["development_roadmap"]: _render_development_roadmap(model),
        OUTPUT_DOCS["roadmap_execution"]: _render_roadmap_execution(model),
        OUTPUT_DOCS["cloud"]: _render_cloud_doc(model),
        OUTPUT_DOCS["cloud_worker"]: _render_cloud_doc(model).replace("# Cloud Status", "# Cloud Worker Status"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write docs to disk")
    args = parser.parse_args()

    model = yaml.safe_load(MODEL_PATH.read_text(encoding="utf-8"))
    rendered = render_docs(model)

    changed: list[Path] = []
    for path, content in rendered.items():
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != content:
            changed.append(path)
            if args.write:
                path.write_text(content, encoding="utf-8")

    if changed and not args.write:
        print("Generated strategy docs are out of sync:")
        for path in changed:
            print(f" - {path.relative_to(ROOT)}")
        return 1

    if args.write:
        print("Updated strategy docs:" if changed else "Strategy docs already up to date.")
        for path in changed:
            print(f" - {path.relative_to(ROOT)}")
    else:
        print("Strategy docs sync check passed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
