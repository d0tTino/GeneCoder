#!/usr/bin/env python3
"""Render strategy documentation sections from docs/strategy_model.yaml."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "docs" / "strategy_model.yaml"

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
}


def _git_head_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Unable to resolve git commit: {result.stderr.strip()}")
    return result.stdout.strip()


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


def _render_product_strategy(model: dict, commit_sha: str) -> str:
    return "\n".join(
        [
            "## Strategy model snapshot (generated)",
            "",
            "> Source of truth: `docs/strategy_model.yaml`",
            f"> last_validated_commit: `{commit_sha}`",
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


def _render_vision(model: dict, commit_sha: str) -> str:
    return "\n".join(
        [
            "## Strategy-aligned phase and capability narrative (generated)",
            "",
            "> Source of truth: `docs/strategy_model.yaml`",
            f"> last_validated_commit: `{commit_sha}`",
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


def _render_development_roadmap(model: dict, commit_sha: str) -> str:
    blocks = [
        "## KPI gates and evidence (generated)",
        "",
        "> Source of truth: `docs/strategy_model.yaml`",
        f"> last_validated_commit: `{commit_sha}`",
        "",
    ]
    for gate in model["kpi_gates"]:
        blocks.extend([f"### {gate['gate']}", "", _format_checks(gate["checks"]), ""])
    return "\n".join(blocks).rstrip()


def render_sections(model: dict, commit_sha: str) -> dict[Path, str]:
    return {
        ROOT / "docs" / "product_strategy.md": _render_product_strategy(model, commit_sha),
        ROOT / "docs" / "vision.md": _render_vision(model, commit_sha),
        ROOT / "docs" / "development_roadmap.md": _render_development_roadmap(model, commit_sha),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="rewrite docs with generated sections")
    args = parser.parse_args()

    model = yaml.safe_load(MODEL_PATH.read_text(encoding="utf-8"))
    commit_sha = _git_head_commit()
    rendered_by_doc = render_sections(model, commit_sha)

    changed_files: list[Path] = []
    for doc_path, rendered in rendered_by_doc.items():
        marker = DOC_CONFIGS[doc_path]["marker"]
        original = doc_path.read_text(encoding="utf-8")
        updated, changed = _replace_marker_block(original, marker, rendered)
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
