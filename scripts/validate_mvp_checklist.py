#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

CHECKLIST_PATH = Path(__file__).resolve().parents[1] / "docs" / "mvp_checklist.md"
CODE_SNIPPET_RE = re.compile(r"`([^`]+)`")
CONFIG_PATH_RE = re.compile(r"configs/[A-Za-z0-9_./-]+\.ya?ml")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_checklist() -> str:
    try:
        return CHECKLIST_PATH.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"Checklist not found at {CHECKLIST_PATH}") from exc


def extract_config_paths(text: str) -> list[str]:
    return sorted(set(CONFIG_PATH_RE.findall(text)))


def extract_cli_commands(text: str) -> list[str]:
    commands: list[str] = []
    for snippet in CODE_SNIPPET_RE.findall(text):
        snippet = snippet.strip()
        if snippet.startswith("genecli"):
            commands.append(snippet)
    return commands


def validate_config_paths(paths: list[str], repo_root: Path) -> list[str]:
    missing = []
    for rel_path in paths:
        if not (repo_root / rel_path).exists():
            missing.append(rel_path)
    return missing


def _prepare_command(tokens: list[str]) -> list[str]:
    if not tokens or tokens[0] != "genecli":
        raise ValueError(f"Unsupported CLI command: {' '.join(tokens)}")
    args = tokens[1:]
    is_bundle = len(args) >= 2 and args[0] == "bundle" and args[1] in {"run", "sweep"}
    if is_bundle:
        if "--dry-run" not in args:
            args.append("--dry-run")
    else:
        if "--help" not in args and "-h" not in args:
            args.append("--help")
    return [sys.executable, "-m", "genecoder.cli", *args]


def validate_cli_commands(commands: list[str], repo_root: Path) -> list[str]:
    failures: list[str] = []
    env = os.environ.copy()
    pythonpath = str(repo_root / "src")
    if env.get("PYTHONPATH"):
        pythonpath = f"{pythonpath}{os.pathsep}{env['PYTHONPATH']}"
    env["PYTHONPATH"] = pythonpath
    for command in commands:
        tokens = shlex.split(command)
        cmd = _prepare_command(tokens)
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            failures.append(
                "\n".join(
                    [
                        f"Command failed: {command}",
                        f"Exit code: {result.returncode}",
                        f"Stdout: {result.stdout.strip()}",
                        f"Stderr: {result.stderr.strip()}",
                    ]
                )
            )
    return failures


def main() -> int:
    text = load_checklist()
    repo_root = _repo_root()

    config_paths = extract_config_paths(text)
    cli_commands = extract_cli_commands(text)

    errors: list[str] = []

    missing_configs = validate_config_paths(config_paths, repo_root)
    if missing_configs:
        errors.append(
            "Missing config paths:\n" + "\n".join(f"- {path}" for path in missing_configs)
        )

    if not cli_commands:
        errors.append("No genecli commands found in the checklist.")
    else:
        failures = validate_cli_commands(cli_commands, repo_root)
        if failures:
            errors.append("CLI command validation failures:\n" + "\n\n".join(failures))

    if errors:
        sys.stderr.write("\n\n".join(errors) + "\n")
        return 1

    print("MVP checklist validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
