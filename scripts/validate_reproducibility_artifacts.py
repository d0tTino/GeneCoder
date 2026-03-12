from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from genecoder.results.repro_report import load_reproducibility_config


def _required_for_mode(config: Mapping[str, Any], mode: str) -> list[str]:
    required = config.get("required_artifacts")
    if not isinstance(required, Mapping):
        return []
    entries = required.get(mode)
    if not isinstance(entries, list):
        return []
    return [str(item) for item in entries]


def _missing_patterns(root: Path, patterns: list[str]) -> list[str]:
    missing: list[str] = []
    for pattern in patterns:
        matches = list(root.glob(pattern))
        if not matches:
            missing.append(pattern)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate reproducibility artifacts and tolerance outcomes"
    )
    parser.add_argument(
        "--artifact-root", type=Path, required=True, help="Bundle run/sweep directory"
    )
    parser.add_argument(
        "--mode", choices=["bundle_run", "bundle_sweep"], default="bundle_sweep"
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Path to reproducibility report JSON (defaults to <artifact-root>/reproducibility_report.json)",
    )
    parser.add_argument(
        "--config", type=Path, default=None, help="Override reproducibility config path"
    )
    args = parser.parse_args()

    config = load_reproducibility_config(args.config)
    required = _required_for_mode(config, args.mode)
    missing = _missing_patterns(args.artifact_root, required)
    if missing:
        raise SystemExit(f"Missing reproducibility artifacts: {', '.join(missing)}")

    report_path = args.report_path or (
        args.artifact_root / "reproducibility_report.json"
    )
    if not report_path.exists():
        raise SystemExit(f"Reproducibility report not found: {report_path}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    summary = (
        report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    )
    if not bool(summary.get("pass", False)):
        tol = summary.get("tolerance_violations", 0)
        det = summary.get("deterministic_violations", 0)
        raise SystemExit(
            f"Reproducibility validation failed: tolerance_violations={tol}, deterministic_violations={det}"
        )

    print("Reproducibility artifacts validated successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
