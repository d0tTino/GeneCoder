#!/usr/bin/env python3
"""Lightweight smoke check for critical docs CLI snippets."""

from __future__ import annotations

from pathlib import Path
import shlex
import subprocess
import sys

DOC_COMMANDS: dict[str, tuple[str, ...]] = {
    "docs/reproducibility.md": (
        "genecli pipeline input.txt decoded.txt --channel illumina --illumina-profile miseq --seed 12345",
    ),
    "docs/channel_profiles.md": (
        "genecli pipeline input.bin decoded.bin --codec reverse --channel illumina --illumina-profile hiseq --seed 12345",
        "genecli pipeline input.bin decoded.bin --codec reverse --channel nanopore --nanopore-profile r10 --seed 12345",
    ),
}


def _check_command_visible(doc_path: Path, command: str) -> None:
    content = doc_path.read_text(encoding="utf-8")
    if command not in content:
        raise AssertionError(f"Missing expected command in {doc_path}: {command}")


def _check_flags_on_help(command: str) -> None:
    args = shlex.split(command)
    if len(args) < 2 or args[0] != "genecli" or args[1] != "pipeline":
        return
    help_proc = subprocess.run(
        [sys.executable, "-m", "genecoder.cli.cli", "pipeline", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    help_text = help_proc.stdout
    for flag in ("--illumina-profile", "--nanopore-profile", "--seed"):
        if flag in command and flag not in help_text:
            raise AssertionError(f"Missing expected flag {flag} in pipeline help output")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    for relative, commands in DOC_COMMANDS.items():
        doc_path = root / relative
        for command in commands:
            _check_command_visible(doc_path, command)
            _check_flags_on_help(command)
    print("Docs command smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
