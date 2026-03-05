#!/usr/bin/env python3
"""Validate generated capability status sections against docs/capabilities.yaml."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs" / "capabilities.yaml"

DOC_CONFIGS = {
    ROOT / "docs" / "vision.md": {
        "marker": "capabilities:vision-status",
        "sections": [
            ("vision_capability_status", "## Capability status snapshot (generated from `docs/capabilities.yaml`)"),
        ],
    },
}


def _collect_missing_matrix_paths(matrix: dict, root: Path) -> list[str]:
    missing: list[str] = []
    for capability in matrix.get("capabilities", []):
        capability_id = capability.get("id", "<unknown>")
        for owner_module in capability.get("owner_modules", []):
            if not isinstance(owner_module, str) or not owner_module.strip():
                missing.append(
                    f"{capability_id}: owner_modules -> <missing or invalid path entry>"
                )
                continue
            if not (root / owner_module).exists():
                missing.append(f"{capability_id}: owner_modules -> {owner_module}")
        for artifact in capability.get("validation_artifacts", []):
            artifact_path = artifact.get("path")
            if not isinstance(artifact_path, str) or not artifact_path.strip():
                missing.append(
                    f"{capability_id}: validation_artifacts.path -> <missing or invalid path entry>"
                )
                continue
            if not (root / artifact_path).exists():
                missing.append(
                    f"{capability_id}: validation_artifacts.path -> {artifact_path}"
                )
    return missing


def _artifact_list(capability: dict) -> str:
    entries = capability.get("validation_artifacts", [])
    if not entries:
        return "_No artifacts listed_"
    return ", ".join(f"`{entry['path']}`" for entry in entries)


def _render_table(title: str, capabilities: list[dict]) -> str:
    lines = [
        title,
        "",
        "| Capability | Status | Phase | Owner modules | Validation artifacts |",
        "| --- | --- | --- | --- | --- |",
    ]
    for cap in capabilities:
        owners = "<br>".join(f"`{path}`" for path in cap.get("owner_modules", [])) or "_Unspecified_"
        lines.append(
            f"| {cap['name']} | `{cap['status']}` | {cap['phase']} | {owners} | {_artifact_list(cap)} |"
        )
    return "\n".join(lines)


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="rewrite docs with generated sections")
    args = parser.parse_args()

    matrix = yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8"))
    missing_matrix_paths = _collect_missing_matrix_paths(matrix, ROOT)
    if missing_matrix_paths:
        print("Missing files referenced by docs/capabilities.yaml:")
        for entry in missing_matrix_paths:
            print(f" - {entry}")
        return 1

    caps_by_id = {item["id"]: item for item in matrix.get("capabilities", [])}
    strategy_sections = matrix.get("strategy_sections", {})

    changed_files: list[Path] = []
    for doc_path, cfg in DOC_CONFIGS.items():
        rendered_blocks = []
        for section_key, title in cfg["sections"]:
            include_ids = strategy_sections[section_key]["include_ids"]
            selected = [caps_by_id[item_id] for item_id in include_ids]
            rendered_blocks.append(_render_table(title, selected))

        rendered = "\n\n".join(rendered_blocks)

        original = doc_path.read_text(encoding="utf-8")
        updated, changed = _replace_marker_block(original, cfg["marker"], rendered)
        if changed:
            if args.write:
                doc_path.write_text(updated, encoding="utf-8")
                changed_files.append(doc_path)
            else:
                print(f"Out-of-sync generated capability section in {doc_path.relative_to(ROOT)}")
                return 1

    print("Capability matrix/doc sync check passed." if not changed_files else "Updated generated sections:")
    for path in changed_files:
        print(f" - {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
