"""Wrapper for optional nanopore read simulators."""
from __future__ import annotations

import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path
import logging
from typing import Callable

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


def _simulate_adapter(command: str, sequence: str, error_rate: float) -> str:
    """Return ``sequence`` processed by an external ``command`` if available."""
    if shutil.which(command):
        try:
            return _run_external(command, sequence)
        except subprocess.CalledProcessError as exc:  # pragma: no cover - error path
            logger.warning(
                "%s failed with return code %s; falling back to simple error model",
                command,
                exc.returncode,
            )
    return simulate_errors(sequence, error_rate)


def simulate_nanopore(sequence: str, error_rate: float = 0.05) -> str:
    """Use ``d2sim`` if available, else fall back to :func:`simulate_errors`."""

    return _simulate_adapter("d2sim", sequence, error_rate)


def simulate_dnarsim(sequence: str, error_rate: float = 0.05) -> str:
    """Use ``dnarsim`` if available, else fall back to :func:`simulate_errors`."""

    return _simulate_adapter("dnarsim", sequence, error_rate)


def simulate_squigulator(sequence: str, error_rate: float = 0.05) -> str:
    """Use ``squigulator`` if available, else fall back to :func:`simulate_errors`."""

    return _simulate_adapter("squigulator", sequence, error_rate)


SIMULATOR_ADAPTERS: dict[str, Callable[[str, float], str]] = {
    "nanopore": simulate_nanopore,
    "dnarsim": simulate_dnarsim,
    "squigulator": simulate_squigulator,
}


def simulate_reads(sequence: str, simulator: str, error_rate: float = 0.05) -> str:
    """Return ``sequence`` corrupted using the chosen simulator.

    If the requested simulator command isn't available, fall back to a simple
    substitution error model implemented in :func:`simulate_errors`.
    """

    if simulator == "none":
        return sequence

    seed_env = os.getenv("GENECODER_SIM_SEED")
    if seed_env is not None:
        random.seed(int(seed_env))

    try:
        adapter = SIMULATOR_ADAPTERS[simulator]
    except KeyError as exc:
        raise ValueError(f"Unknown simulator: {simulator}") from exc

    return adapter(sequence, error_rate)
