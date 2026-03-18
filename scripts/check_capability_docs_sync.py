#!/usr/bin/env python3
"""Validate generated capabilities metadata references."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs" / "capabilities.yaml"


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="reserved for compatibility")
    parser.parse_args()

    matrix = yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8"))
    missing_matrix_paths = _collect_missing_matrix_paths(matrix, ROOT)
    if missing_matrix_paths:
        print("Missing files referenced by docs/capabilities.yaml:")
        for entry in missing_matrix_paths:
            print(f" - {entry}")
        return 1

    print("Capability metadata sync check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
