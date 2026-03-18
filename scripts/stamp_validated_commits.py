#!/usr/bin/env python3
"""Stamp strategy and roadmap docs with the current Git HEAD commit."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_TO_STAMP = (
    ROOT / "docs" / "product_strategy.md",
    ROOT / "docs" / "development_roadmap.md",
    ROOT / "docs" / "roadmap_execution.md",
    ROOT / "docs" / "cloud.md",
    ROOT / "docs" / "cloud_worker.md",
)
STAMP_PATTERN = re.compile(r"(last_validated_commit:\s*`)([0-9a-f]{7,40})(`)")


def git_head_commit() -> str:
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


def stamp_content(content: str, commit_sha: str) -> tuple[str, bool]:
    updated, replacements = STAMP_PATTERN.subn(rf"\g<1>{commit_sha}\g<3>", content)
    if replacements == 0:
        raise ValueError("No last_validated_commit field found.")
    return updated, updated != content


def stamp_docs(commit_sha: str, write: bool) -> list[Path]:
    changed: list[Path] = []
    for doc_path in DOCS_TO_STAMP:
        original = doc_path.read_text(encoding="utf-8")
        updated, did_change = stamp_content(original, commit_sha)
        if did_change:
            changed.append(doc_path)
            if write:
                doc_path.write_text(updated, encoding="utf-8")
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="rewrite docs with the current HEAD commit")
    args = parser.parse_args(argv)

    commit_sha = git_head_commit()
    changed = stamp_docs(commit_sha, write=args.write)

    if args.write:
        print("Stamped last_validated_commit fields:" if changed else "Docs already stamped with the current HEAD commit.")
        for path in changed:
            print(f" - {path.relative_to(ROOT)}")
        return 0

    if changed:
        print("Docs are not stamped with the current HEAD commit:")
        for path in changed:
            print(f" - {path.relative_to(ROOT)}")
        print("Run `python scripts/stamp_validated_commits.py --write` after required QA jobs pass.")
        return 1

    print("All stamped docs already match the current HEAD commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
