#!/usr/bin/env python
"""Generate a dependency availability report for optional integration tests."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class DependencyStatus:
    name: str
    kind: str
    required_by: str
    available: bool
    detail: str


PYTHON_DEPS = {
    "pyldpc": "LDPC/FEC integration tests",
    "pyfinite": "fountain-code integration tests",
    "bchlib": "BCH integration tests",
    "raptorq": "RaptorQ integration tests",
    "dnachisel": "DNA Chisel integration tests",
    "chamaeleo": "Chamaeleo codec integration tests",
    "deepdna": "DeepDNA codec integration tests",
    "fastapi": "web API integration tests",
    "fastapi_limiter": "web API limiter integration tests",
    "httpx": "web API client integration tests",
    "flet": "GUI integration tests",
    "streamlit": "dashboard integration tests",
    "playwright": "frontend browser integration tests",
    "mpi4py": "MPI integration tests",
    "cryptography": "security and signing integration tests",
}

EXECUTABLE_DEPS = {
    "d2sim": "external simulator integration tests",
    "dnarsim": "external simulator integration tests",
    "squigulator": "external simulator integration tests",
}


def build_report() -> list[DependencyStatus]:
    report: list[DependencyStatus] = []
    for module, purpose in sorted(PYTHON_DEPS.items()):
        spec = importlib.util.find_spec(module)
        report.append(
            DependencyStatus(
                name=module,
                kind="python-module",
                required_by=purpose,
                available=spec is not None,
                detail="importable" if spec else "missing",
            )
        )
    for exe, purpose in sorted(EXECUTABLE_DEPS.items()):
        resolved = shutil.which(exe)
        report.append(
            DependencyStatus(
                name=exe,
                kind="executable",
                required_by=purpose,
                available=resolved is not None,
                detail=resolved or "missing",
            )
        )
    return report


def render_markdown(rows: list[DependencyStatus]) -> str:
    lines = [
        "# Optional integration dependency report",
        "",
        "| Dependency | Kind | Required by | Available | Detail |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row.name}` | {row.kind} | {row.required_by} | "
            f"{'yes' if row.available else 'no'} | {row.detail} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="artifacts/optional-integration-dependency-report.md",
        help="Path to write markdown dependency report.",
    )
    parser.add_argument(
        "--json-output",
        default="artifacts/optional-integration-dependency-report.json",
        help="Path to write JSON dependency report.",
    )
    args = parser.parse_args()

    rows = build_report()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(rows), encoding="utf-8")

    json_path = Path(args.json_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps([asdict(row) for row in rows], indent=2), encoding="utf-8"
    )

    print(output_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
