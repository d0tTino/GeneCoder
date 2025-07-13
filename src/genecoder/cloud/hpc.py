from __future__ import annotations

import re
import subprocess


def generate_slurm_script(
    command: str,
    *,
    job_name: str = "genecoder",
    time: str = "01:00:00",
    partition: str | None = None,
    output: str | None = None,
) -> str:
    """Return a simple Slurm batch script.

    ``command`` must not contain newlines or shell metacharacters such as
    ``;``, ``&&`` or ``|``. This prevents accidental command injection when the
    script is written to disk.
    """
    if any(c in command for c in "\n\r"):
        raise ValueError("command must not contain newlines")
    if re.search(r"[;&|<>`$]", command):
        raise ValueError("command contains unsafe characters")

    allowed = re.compile(r"^[A-Za-z0-9_-]+$")
    if not allowed.fullmatch(job_name):
        raise ValueError("job_name contains invalid characters")
    if partition is not None and not allowed.fullmatch(partition):
        raise ValueError("partition contains invalid characters")

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
    proc = subprocess.run(
        [sbatch], input=script, text=True, capture_output=True, check=True
    )
    match = re.search(r"Submitted batch job (\d+)", proc.stdout)
    if not match:
        raise RuntimeError("Failed to parse sbatch output")
    return match.group(1)
