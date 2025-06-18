"""Wrapper for optional nanopore read simulators."""
from __future__ import annotations

import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

from .channel_sim import simulate_errors
from .formats import from_fasta, to_fasta


def _run_external(command: str, sequence: str) -> str:
    """Run an external simulator command on ``sequence``.

    The command must accept an input FASTA file and output FASTA to a
    second file: ``command <in> <out>``.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "input.fasta"
        output_path = Path(tmpdir) / "output.fasta"
        input_path.write_text(to_fasta(sequence, "seq"))
        subprocess.run([command, str(input_path), str(output_path)], check=True)
        records = from_fasta(output_path.read_text())
        if not records:
            raise RuntimeError(f"{command} produced no FASTA output")
        return records[0][1]


def simulate_reads(sequence: str, simulator: str, error_rate: float = 0.05) -> str:
    """Return ``sequence`` corrupted using the chosen simulator.

    If the requested simulator command isn't available, fall back to a simple
    substitution error model implemented in :func:`simulate_errors`.
    ``simulator`` may be ``none``, ``nanopore``, ``dnarsim`` or ``squigulator``.
    """
    if simulator == "none":
        return sequence

    seed_env = os.getenv("GENECODER_SIM_SEED")
    if seed_env is not None:
        random.seed(int(seed_env))

    if simulator == "nanopore":
        if shutil.which("d2sim"):
            try:
                return _run_external("d2sim", sequence)
            except subprocess.CalledProcessError as exc:  # pragma: no cover - error path
                logger.warning(
                    "d2sim failed with return code %s; falling back to simple error model",
                    exc.returncode,
                )
                return simulate_errors(sequence, error_rate)
        return simulate_errors(sequence, error_rate)

    if simulator == "dnarsim":
        if shutil.which("dnarsim"):
            try:
                return _run_external("dnarsim", sequence)
            except subprocess.CalledProcessError as exc:  # pragma: no cover - error path
                logger.warning(
                    "dnarsim failed with return code %s; falling back to simple error model",
                    exc.returncode,
                )
                return simulate_errors(sequence, error_rate)
        return simulate_errors(sequence, error_rate)

    if simulator == "squigulator":
        if shutil.which("squigulator"):
            try:
                return _run_external("squigulator", sequence)
            except subprocess.CalledProcessError as exc:  # pragma: no cover - error path
                logger.warning(
                    "squigulator failed with return code %s; falling back to simple error model",
                    exc.returncode,
                )
                return simulate_errors(sequence, error_rate)
        return simulate_errors(sequence, error_rate)

    raise ValueError(f"Unknown simulator: {simulator}")


from typing import Callable, Any


def register(register_simulator: Callable[[str, Callable[..., Any]], None]) -> None:
    """Register the builtin simulators."""

    def _wrap(name: str) -> Callable[[str, float], str]:
        def simulate(seq: str, error_rate: float = 0.05) -> str:
            return simulate_reads(seq, name, error_rate)

        return simulate

    for name in ("none", "nanopore", "dnarsim", "squigulator"):
        register_simulator(name, _wrap(name))
