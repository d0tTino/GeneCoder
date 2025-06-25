"""Wrapper for optional nanopore read simulators."""
from __future__ import annotations

import random
import shutil
import subprocess
import tempfile
from pathlib import Path
import logging
from typing import Callable, Sequence

__all__ = [
    "simulate_d2sim",
    "simulate_dnarsim",
    "simulate_squigulator",
    "simulate_reads",
    "Channel",
]

from .channels.base import BaseChannel

logger = logging.getLogger(__name__)

from .random_utils import make_rng
from .channel_sim import simulate_errors
from .formats import from_fasta, to_fasta




def _run_external(command: Sequence[str] | str, sequence: str) -> str:
    """Run an external simulator command on ``sequence``.

    The command must accept an input FASTA file and output FASTA to a
    second file: ``command <in> <out>``.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "input.fasta"
        output_path = Path(tmpdir) / "output.fasta"
        input_path.write_text(to_fasta(sequence, "seq"))
        cmd_list = [command] if isinstance(command, str) else list(command)
        subprocess.run(cmd_list + [str(input_path), str(output_path)], check=True)
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
            cmd_list = [command]
            if command == "d2sim":
                cmd_list += ["-e", str(error_rate)]
            return _run_external(cmd_list, sequence)
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
        rng = make_rng()
    return simulate_errors(sequence, error_rate, rng=rng)



def simulate_d2sim(
    sequence: str,
    error_rate: float = 0.05,
    rng: random.Random | None = None,
) -> str:
    """Use ``d2sim`` if available, else fall back to :func:`simulate_errors`."""



    if rng is None:
        rng = make_rng()

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
        rng = make_rng()

    return _simulate_adapter("dnarsim", sequence, error_rate, rng)


def simulate_squigulator(
    sequence: str, error_rate: float = 0.05, rng: random.Random | None = None
) -> str:
    """Use ``squigulator`` if available, else fall back to :func:`simulate_errors`.


    ``rng`` provides the randomness source for the fallback simulator.
    """


    if rng is None:
        rng = make_rng()

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
    """Return ``sequence`` corrupted using the chosen simulator."""

    from .plugins import SIMULATOR_REGISTRY

    try:
        channel = SIMULATOR_REGISTRY[simulator]
    except KeyError as exc:
        raise ValueError(f"Unknown simulator: {simulator}") from exc

    if hasattr(channel, "error_rate"):
        old_rate = channel.error_rate
        channel.error_rate = error_rate
        try:
            return channel.simulate(sequence)
        finally:
            channel.error_rate = old_rate
    return channel.simulate(sequence)


class Channel(BaseChannel):
    """Adapter implementing :class:`BaseChannel` for built-in simulators."""

    def __init__(self, name: str, error_rate: float = 0.05) -> None:
        self.name = name
        self.error_rate = error_rate

    def simulate(self, sequence: str) -> str:
        adapter = SIMULATOR_ADAPTERS[self.name]
        return adapter(sequence, self.error_rate, make_rng())



def register(register_simulator: Callable[[str, BaseChannel], None]) -> None:
    """Register the builtin simulators."""

    for name in SIMULATOR_ADAPTERS:
        register_simulator(name, Channel(name))


