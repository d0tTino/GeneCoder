#!/usr/bin/env python
"""Check if Python code changes are limited to comments or documentation."""
import os
import subprocess


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.stdout


def is_comment_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("#"):
        return True
    if '"""' in stripped or "'''" in stripped:
        return True
    return False


def only_comments_changed(base_ref: str) -> bool:
    # List python files changed compared to base_ref
    files = run(["git", "diff", "--name-only", base_ref, "--", "*.py"]).splitlines()
    if not files:
        return True
    diff = run(["git", "diff", base_ref, "--unified=0", "--", *files])
    for line in diff.splitlines():
        if not line.startswith(("+", "-")):
            continue
        if line.startswith(("+++", "---")):
            continue
        content = line[1:]
        if not is_comment_line(content):
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
