#!/usr/bin/env python
"""Fail if any glossary term is missing from the markdown docs."""
from __future__ import annotations

import json
import re
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    docs_dir = repo_root / "docs"
    glossary_path = docs_dir / "glossary.json"

    with glossary_path.open("r", encoding="utf-8") as fh:
        terms: list[str] = list(json.load(fh).keys())

    md_files = list(docs_dir.glob("*.md"))
    missing: list[str] = []
    for term in terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        found = False
        for md_file in md_files:
            text = md_file.read_text(encoding="utf-8")
            if pattern.search(text):
                found = True
                break
        if not found:
            missing.append(term)

    if missing:
        print("Missing glossary terms: " + ", ".join(sorted(missing)))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
