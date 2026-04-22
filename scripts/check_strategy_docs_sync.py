#!/usr/bin/env python3
"""Fail when generated strategy sections drift from docs/strategy_model.yaml."""

from __future__ import annotations

import json
import re
import sys

from render_strategy_docs import ROOT, VALIDATION_PATH, main as render_main

DOCS_TO_VERIFY = (
    ROOT / "docs" / "product_strategy.md",
    ROOT / "docs" / "development_roadmap.md",
    ROOT / "docs" / "vision.md",
    ROOT / "docs" / "roadmap_execution.md",
)
COMMIT_PATTERN = re.compile(r"last_validated_commit:\s*`([0-9a-f]{7,40})`")


def _load_validation_commit() -> str:
    if not VALIDATION_PATH.exists():
        raise FileNotFoundError(
            "Missing docs/strategy_validation.json. "
            "Run `python scripts/generate_strategy_artifacts.py --write`."
        )

    payload = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))
    commit = payload.get("last_validated_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{7,40}", commit):
        raise ValueError(
            "docs/strategy_validation.json contains an invalid last_validated_commit. "
            "Run `python scripts/generate_strategy_artifacts.py --write`."
        )
    return commit


def _verify_embedded_commits() -> int:
    expected_commit = _load_validation_commit()
    failures: list[str] = []

    for doc_path in DOCS_TO_VERIFY:
        content = doc_path.read_text(encoding="utf-8")
        found_commits = COMMIT_PATTERN.findall(content)
        if not found_commits:
            failures.append(f"{doc_path.relative_to(ROOT)} (missing last_validated_commit)")
            continue

        divergent = sorted({commit for commit in found_commits if commit != expected_commit})
        if divergent:
            failures.append(
                f"{doc_path.relative_to(ROOT)} (expected {expected_commit}, found {', '.join(divergent)})"
            )

    if failures:
        print("Strategy docs embed divergent last_validated_commit values:")
        for failure in failures:
            print(f" - {failure}")
        print("Regenerate with `python scripts/generate_strategy_artifacts.py --write`.")
        return 1

    return 0


def main() -> int:
    render_status = render_main()
    if render_status != 0:
        return render_status
    return _verify_embedded_commits()


if __name__ == "__main__":
    sys.exit(main())
