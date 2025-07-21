from __future__ import annotations

import re
import subprocess

_UNSAFE_RE = re.compile(r"[;&|<>`$(){}\[\]*?!~]")


def _validate_safe(value: str, field: str) -> None:
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f"{field} contains control characters")
    if _UNSAFE_RE.search(value):
        raise ValueError(f"{field} contains unsafe characters")


def generate_slurm_script(
    command: str,
    *,
    job_name: str = "genecoder",
    time: str = "01:00:00",
    partition: str | None = None,
    output: str | None = None,
) -> str:
    """Return a simple Slurm batch script.

    ``command`` as well as ``job_name``, ``partition`` and ``output`` are
    validated to ensure they do not contain control characters or common shell
    metacharacters. This prevents accidental command injection when the script
    is written to disk.
    """
    if any(c in command for c in "\n\r"):
        raise ValueError("command must not contain newlines")
    _validate_safe(command, "command")

    allowed = re.compile(r"^[A-Za-z0-9_-]+$")
    _validate_safe(job_name, "job_name")
    if not allowed.fullmatch(job_name):
        raise ValueError("job_name contains invalid characters")
    if partition is not None:
        _validate_safe(partition, "partition")
        if not allowed.fullmatch(partition):
            raise ValueError("partition contains invalid characters")
    if output is not None:
        _validate_safe(output, "output")

    lines = ["#!/bin/bash", f"#SBATCH --job-name={job_name}"]
    lines.append(f"#SBATCH --output={output or '%x-%j.out'}")
    if partition:
        lines.append(f"#SBATCH --partition={partition}")
    if time:
        lines.append(f"#SBATCH --time={time}")
    lines.append("")
    lines.append(command)
    lines.append("")
    return "\n".join(lines)


def submit_slurm_job(script: str, sbatch: str = "sbatch") -> str:
    """Submit the script via ``sbatch`` and return the job ID."""
    try:
        proc = subprocess.run(
            [sbatch], input=script, text=True, capture_output=True, check=True
        )
    except FileNotFoundError as exc:
        raise RuntimeError("sbatch not found") from exc
    match = re.search(r"Submitted batch job (\d+)", proc.stdout)
    if not match:
        raise RuntimeError("Failed to parse sbatch output")
    return match.group(1)
