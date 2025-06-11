#!/usr/bin/env python
"""Check if repository changes are limited to docs or Python comments."""
from __future__ import annotations

import io
import os
import subprocess
import tokenize


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.stdout

def _tokens_without_comments(source: str) -> list[tuple[int, str]] | None:
    """Return tokens excluding comments and NL tokens."""

    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        return [
            (tok.type, tok.string)
            for tok in tokens
            if tok.type not in (tokenize.COMMENT, tokenize.NL, tokenize.ENCODING)
        ]
    except tokenize.TokenError:
        return None


def only_comments_changed(base_ref: str) -> bool:
    """Return True if only docs or Python comments changed."""

    all_files = run(["git", "diff", "--name-only", base_ref]).splitlines()
    if not all_files:
        return True

    for path in all_files:
        if path.endswith(('.md', '.rst')) or path.startswith('docs/'):
            continue
        if path.endswith('.py'):
            old_src = run(["git", "show", f"{base_ref}:{path}"])
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    new_src = fh.read()
            except FileNotFoundError:
                new_src = ""

            old_tokens = _tokens_without_comments(old_src)
            new_tokens = _tokens_without_comments(new_src)
            if old_tokens is None or new_tokens is None or old_tokens != new_tokens:
                return False
        else:
            return False

    return True


def main() -> int:
    base_ref = os.environ.get("BASE_SHA", "origin/main")
    only_comments = only_comments_changed(base_ref)
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a") as fh:
            fh.write(f"only_comments={str(only_comments).lower()}\n")
    else:
        print(f"only_comments={str(only_comments).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
