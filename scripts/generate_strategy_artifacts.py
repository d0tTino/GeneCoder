#!/usr/bin/env python3
"""Generate all strategy-derived docs from docs/strategy_model.yaml."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "docs" / "strategy_model.yaml"
CAPABILITIES_PATH = ROOT / "docs" / "capabilities.yaml"
CI_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "python-ci.yml"
BADGES_PATH = ROOT / "docs" / "capability_maturity_badges.md"

GENERATED_YAML_HEADER = [
    "# GENERATED FILE - DO NOT EDIT DIRECTLY.",
    "# Canonical source: docs/strategy_model.yaml",
    "# Regenerate with: python scripts/generate_strategy_artifacts.py --write",
]


class _IndentedSafeDumper(yaml.SafeDumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        super().increase_indent(flow, False)


def _load_model() -> dict:
    return yaml.safe_load(MODEL_PATH.read_text(encoding="utf-8"))


def _render_generated_yaml(data: dict) -> str:
    body = yaml.dump(data, Dumper=_IndentedSafeDumper, sort_keys=False, default_flow_style=False)
    return "\n".join(GENERATED_YAML_HEADER) + "\n" + body


def render_capabilities_yaml(model: dict) -> str:
    payload = {
        "version": model["version"],
        "last_updated": model.get("last_updated", "generated-from-strategy-model"),
        "capabilities": [
            {
                key: capability[key]
                for key in (
                    "id",
                    "name",
                    "status",
                    "phase",
                    "owner_modules",
                    "validation_artifacts",
                    "ci_status_checks",
                )
                if key in capability
            }
            for capability in model.get("feature_capabilities", [])
            if capability.get("status") != "deprecated"
        ],
        "strategy_sections": model.get("strategy_sections", {}),
        "phase_gates": model.get("phase_gates", []),
    }
    return _render_generated_yaml(payload)


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, cwd=ROOT, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"command failed: {cmd}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="rewrite generated artifacts")
    args = parser.parse_args()

    model = _load_model()
    rendered_capabilities = render_capabilities_yaml(model)

    existing = CAPABILITIES_PATH.read_text(encoding="utf-8") if CAPABILITIES_PATH.exists() else ""
    if existing != rendered_capabilities:
        if not args.write:
            print("Generated capabilities metadata is out of date. Run:")
            print("  python scripts/generate_strategy_artifacts.py --write")
            return 1
        CAPABILITIES_PATH.write_text(rendered_capabilities, encoding="utf-8")

    try:
        if args.write:
            _run([sys.executable, "scripts/render_strategy_docs.py", "--write"])
            _run([sys.executable, "scripts/render_capability_maturity_badges.py", "--write"])
        else:
            _run([sys.executable, "scripts/check_strategy_docs_sync.py"])
            _run([sys.executable, "scripts/render_capability_maturity_badges.py"])
    except RuntimeError as exc:
        print(str(exc))
        return 1

    print("Generated strategy artifacts updated." if args.write else "Generated strategy artifacts are up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
