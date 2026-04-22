#!/usr/bin/env python3
"""Render strategy documentation sections from docs/strategy_model.yaml."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "docs" / "strategy_model.yaml"
VALIDATION_PATH = ROOT / "docs" / "strategy_validation.json"

DOC_CONFIGS = {
    ROOT / "docs" / "product_strategy.md": {
        "marker": "strategy:product",
    },
    ROOT / "docs" / "vision.md": {
        "marker": "strategy:vision",
    },
    ROOT / "docs" / "development_roadmap.md": {
        "marker": "strategy:roadmap",
    },
    ROOT / "docs" / "roadmap_execution.md": {
        "marker": "strategy:execution",
    },
}

GENERATED_HEADER = (
    "<!-- GENERATED FILE: derived from docs/strategy_model.yaml; "
    "edit docs/strategy_model.yaml and rerun "
    "`python scripts/generate_strategy_artifacts.py --write`. -->"
)


def load_strategy_validation() -> dict[str, str]:
    if not VALIDATION_PATH.exists():
        raise FileNotFoundError(
            "Missing docs/strategy_validation.json. "
            "Run `python scripts/generate_strategy_artifacts.py --write`."
        )

    payload = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))
    required_keys = {"last_validated_commit", "generated_at", "generator_version"}
    missing = sorted(required_keys - payload.keys())
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(
            f"docs/strategy_validation.json is missing required keys: {missing_text}. "
            "Run `python scripts/generate_strategy_artifacts.py --write`."
        )
    return payload


def _replace_marker_block(content: str, marker: str, new_block: str) -> tuple[str, bool]:
    start = f"<!-- {marker}:start -->"
    end = f"<!-- {marker}:end -->"
    if start not in content or end not in content:
        raise ValueError(f"Missing marker block {start} ... {end}")

    prefix, rest = content.split(start, 1)
    middle, suffix = rest.split(end, 1)
    replacement = f"{start}\n{new_block}\n{end}"
    updated = f"{prefix}{replacement}{suffix}"
    return updated, middle.strip() != new_block.strip()


def ensure_generated_header(content: str) -> tuple[str, bool]:
    if content.startswith(GENERATED_HEADER):
        return content, False
    return f"{GENERATED_HEADER}\n\n{content.lstrip()}", True


def _format_checks(checks: list[dict]) -> str:
    lines = ["| Metric | Threshold | Evidence |", "| --- | --- | --- |"]
    for check in checks:
        evidence = ", ".join(f"`{item}`" for item in check.get("evidence", [])) or "_None listed_"
        lines.append(f"| {check['metric']} | {check['threshold']} | {evidence} |")
    return "\n".join(lines)


def _render_capability_table(capabilities: list[dict]) -> str:
    lines = ["| Capability | Status | Phase | Owner modules |", "| --- | --- | --- | --- |"]
    for capability in capabilities:
        owners = "<br>".join(f"`{path}`" for path in capability.get("owner_modules", [])) or "_Unspecified_"
        lines.append(
            f"| {capability['name']} | `{capability['status']}` | {capability['phase']} | {owners} |"
        )
    return "\n".join(lines)


def _provenance_lines(validation: dict[str, str]) -> list[str]:
    return [
        "> Source of truth: `docs/strategy_model.yaml`",
        "> Validation provenance: `docs/strategy_validation.json`",
        f"> last_validated_commit: `{validation['last_validated_commit']}`",
        f"> generated_at: `{validation['generated_at']}`",
        f"> generator_version: `{validation['generator_version']}`",
    ]


def _render_product_strategy(model: dict, validation: dict[str, str]) -> str:
    return "\n".join(
        [
            "## Strategy model snapshot (generated)",
            "",
            *_provenance_lines(validation),
            "",
            "### Phase definitions",
            "",
            "| Phase | Name | Objective | Execution focus |",
            "| --- | --- | --- | --- |",
            *[
                f"| {phase['id']} | {phase['name']} | {phase['objective']} | {phase['execution_focus']} |"
                for phase in model["phases"]
            ],
            "",
            "### Feature capability statuses",
            "",
            _render_capability_table(model["feature_capabilities"]),
            "",
            "### Deployment posture flags",
            "",
            "| Flag | Value |",
            "| --- | --- |",
            *[f"| `{flag}` | `{value}` |" for flag, value in model["deployment_posture"].items()],
        ]
    )


def _render_vision(model: dict, validation: dict[str, str]) -> str:
    return "\n".join(
        [
            "## Strategy-aligned phase and capability narrative (generated)",
            "",
            *_provenance_lines(validation),
            "",
            "### Phase intent",
            "",
            *[
                f"- **Phase {phase['id']} — {phase['name']}**: {phase['objective']} "
                f"(Execution focus: {phase['execution_focus']})"
                for phase in model["phases"]
            ],
            "",
            "### Capability status snapshot",
            "",
            _render_capability_table(model["feature_capabilities"]),
        ]
    )


def _render_development_roadmap(model: dict, validation: dict[str, str]) -> str:
    blocks = [
        "## KPI gates and evidence (generated)",
        "",
        *_provenance_lines(validation),
        "",
    ]
    for gate in model["kpi_gates"]:
        blocks.extend([f"### {gate['gate']}", "", _format_checks(gate["checks"]), ""])
    return "\n".join(blocks).rstrip()


def _render_roadmap_execution(model: dict, validation: dict[str, str]) -> str:
    blocks = [
        "## Execution summary (generated)",
        "",
        *_provenance_lines(validation),
        "",
        "### Phase execution focus",
        "",
        *[
            f"- **Phase {phase['id']} — {phase['name']}**: {phase['execution_focus']}"
            for phase in model["phases"]
        ],
        "",
        "### KPI gate checklist",
        "",
    ]
    for gate in model["kpi_gates"]:
        blocks.append(f"#### {gate['gate']}")
        for check in gate["checks"]:
            blocks.append(f"- {check['metric']}: **{check['threshold']}**")
        blocks.append("")
    return "\n".join(blocks).rstrip()


def render_sections(model: dict, validation: dict[str, str]) -> dict[Path, str]:
    return {
        ROOT / "docs" / "product_strategy.md": _render_product_strategy(model, validation),
        ROOT / "docs" / "vision.md": _render_vision(model, validation),
        ROOT / "docs" / "development_roadmap.md": _render_development_roadmap(model, validation),
        ROOT / "docs" / "roadmap_execution.md": _render_roadmap_execution(model, validation),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="rewrite docs with generated sections")
    args = parser.parse_args()

    model = yaml.safe_load(MODEL_PATH.read_text(encoding="utf-8"))
    validation = load_strategy_validation()
    rendered_by_doc = render_sections(model, validation)

    changed_files: list[Path] = []
    for doc_path, rendered in rendered_by_doc.items():
        marker = DOC_CONFIGS[doc_path]["marker"]
        original = doc_path.read_text(encoding="utf-8")
        updated, changed = _replace_marker_block(original, marker, rendered)
        updated, header_changed = ensure_generated_header(updated)
        changed = changed or header_changed
        if changed:
            if args.write:
                doc_path.write_text(updated, encoding="utf-8")
                changed_files.append(doc_path)
            else:
                print(f"Out-of-sync generated strategy section in {doc_path.relative_to(ROOT)}")
                return 1

    if args.write:
        print("Updated generated strategy sections:" if changed_files else "Generated strategy sections already up to date.")
        for path in changed_files:
            print(f" - {path.relative_to(ROOT)}")
    else:
        print("Strategy doc section sync check passed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
