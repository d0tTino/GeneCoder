"""Wrapper for optional nanopore read simulators."""
from __future__ import annotations

import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path
import logging
from typing import Any, Callable

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


def _simulate_adapter(
    command: str, sequence: str, error_rate: float, rng: random.Random | None
) -> str:

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
    else:
        logger.warning("%s not found; falling back to simple error model", command)
    # use a deterministic local RNG for external simulators and forward it when
    # falling back to :func:`simulate_errors` so calls remain reproducible
    if rng is None:
        rng = random.Random()
    return simulate_errors(sequence, error_rate, rng=rng)



def simulate_d2sim(
    sequence: str,
    error_rate: float = 0.05,
    rng: random.Random | None = None,
) -> str:
    """Use ``d2sim`` if available, else fall back to :func:`simulate_errors`."""



    if rng is None:
        rng = random.Random()

    return _simulate_adapter("d2sim", sequence, error_rate, rng)


# Backwards compatibility alias
simulate_nanopore = simulate_d2sim


def simulate_dnarsim(
    sequence: str, error_rate: float = 0.05, rng: random.Random | None = None
) -> str:
    """Use ``dnarsim`` if available, else fall back to :func:`simulate_errors`.

    ``rng`` is forwarded to :func:`simulate_errors` if the external command is
    unavailable.
    """


    if rng is None:
        rng = random.Random()

    return _simulate_adapter("dnarsim", sequence, error_rate, rng)


def simulate_squigulator(
    sequence: str, error_rate: float = 0.05, rng: random.Random | None = None
) -> str:
    """Use ``squigulator`` if available, else fall back to :func:`simulate_errors`.


    ``rng`` provides the randomness source for the fallback simulator.
    """


    if rng is None:
        rng = random.Random()

    return _simulate_adapter("squigulator", sequence, error_rate, rng)


def simulate_none(
    sequence: str,
    error_rate: float = 0.0,
    rng: random.Random | None = None,
) -> str:

    """Return ``sequence`` unchanged.

    The ``rng`` parameter is accepted for API compatibility but ignored.
    """

    return sequence


SIMULATOR_ADAPTERS: dict[str, Callable[[str, float, random.Random | None], str]] = {

    "d2sim": simulate_d2sim,
    "dnarsim": simulate_dnarsim,
    "squigulator": simulate_squigulator,
    # backward compatibility names
    "nanopore": simulate_d2sim,
    "none": simulate_none,
}


def simulate_reads(sequence: str, simulator: str, error_rate: float = 0.05) -> str:
    """Return ``sequence`` corrupted using the chosen simulator.

    A per-call :class:`~random.Random` instance is used so calls do not affect
    the global RNG.  If the ``GENECODER_SIM_SEED`` environment variable is set,
    it will be used to seed this local RNG.  If the requested simulator command
    isn't available, fall back to a simple substitution error model implemented
    in :func:`simulate_errors`.
    """

    seed_env = os.getenv("GENECODER_SIM_SEED")
    rng = random.Random(int(seed_env)) if seed_env is not None else random.Random()


    try:
        adapter = SIMULATOR_ADAPTERS[simulator]
    except KeyError as exc:
        raise ValueError(f"Unknown simulator: {simulator}") from exc

    return adapter(sequence, error_rate, rng)


def _wrap(name: str) -> Callable[[str, float], str]:
    """Return a simulator function bound to ``name``."""

    def simulate(seq: str, error_rate: float = 0.05) -> str:
        return simulate_reads(seq, name, error_rate)

    return simulate



def register(register_simulator: Callable[[str, Callable[..., Any]], None]) -> None:
    """Register the builtin simulators."""

    for name in SIMULATOR_ADAPTERS:
        register_simulator(name, _wrap(name))


