"""Wrapper for optional nanopore read simulators."""
from __future__ import annotations

import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path
import logging
from typing import Callable, Sequence

from .utils import get_temp_dir

__all__ = [
    "simulate_d2sim",
    "simulate_dnarsim",
    "simulate_squigulator",
    "simulate_reads",
    "Channel",
]

from .api import Simulator
from .simulators import register_simulator as _register_simulator

logger = logging.getLogger(__name__)

from .random_utils import make_rng
from .channel_sim import simulate_errors
from .formats import from_fasta, to_fasta


def _parse_env_options(command: str) -> list[str]:
    """Return additional options for ``command`` parsed from the environment.

    The environment variable ``GENECODER_<CMD>_OPTIONS`` allows forwarding extra
    command line arguments to the external simulators.  For security reasons
    only a limited set of characters is permitted.  If ``raw`` contains
    potentially dangerous characters a ``ValueError`` is raised.
    """

    env_var = f"GENECODER_{command.upper()}_OPTIONS"
    raw = os.getenv(env_var)
    if not raw:
        return []

    import re

    # Reject characters outside a conservative whitelist to avoid
    # command injection via shell metacharacters.
    if not raw.isprintable() or not re.fullmatch(r"[A-Za-z0-9_\-./=:'\"\s]*", raw):
        raise ValueError(f"Unsafe characters in {env_var}")

    import shlex

    try:
        options = shlex.split(raw)
    except ValueError as exc:  # pragma: no cover - error path
        logger.warning("Invalid %s value: %s", env_var, exc)
        return []

    flag_re = re.compile(r"^-{1,2}[A-Za-z0-9][A-Za-z0-9_-]*(=.+)?$")
    arg_re = re.compile(r"^[A-Za-z0-9./:_-]+$")

    for opt in options:
        if opt.startswith("-"):
            if not flag_re.fullmatch(opt):
                raise ValueError(f"Invalid option {opt!r} in {env_var}")
        else:
            if not arg_re.fullmatch(opt):
                raise ValueError(f"Invalid argument {opt!r} in {env_var}")

    logger.debug("Using %s=%r", env_var, options)
    return options




def _run_external(command: Sequence[str] | str, sequence: str) -> str:
    """Run an external simulator command on ``sequence``.

    The command must accept an input FASTA file and output FASTA to a
    second file: ``command <in> <out>``.
    """
    with tempfile.TemporaryDirectory(dir=get_temp_dir()) as tmpdir:
        input_path = Path(tmpdir) / "input.fasta"
        output_path = Path(tmpdir) / "output.fasta"
        input_path.write_text(to_fasta(sequence, "seq"))
        cmd_list = [command] if isinstance(command, str) else list(command)
        full_cmd = cmd_list + [str(input_path), str(output_path)]
        logger.debug("Running external command: %s", " ".join(full_cmd))
        try:
            subprocess.run(full_cmd, check=True)
        except subprocess.CalledProcessError as exc:  # pragma: no cover - error path
            raise RuntimeError(
                f"{cmd_list[0]} failed with exit code {exc.returncode}"
            ) from exc
        records = from_fasta(output_path.read_text())
        if not records:
            raise RuntimeError(f"{cmd_list[0]} produced no FASTA output")
        return records[0][1]


def _simulate_adapter(
    command: str,
    sequence: str,
    error_rate: float,
    rng: random.Random | None,
    extra_args: Sequence[str] | None = None,
) -> str:

    """Return ``sequence`` processed by an external ``command`` if available."""
    if shutil.which(command):
        try:
            cmd_list = [command]
            if command in {"d2sim", "dnarsim", "squigulator"}:
                cmd_list += ["-e", str(error_rate)]
            if extra_args:
                cmd_list += list(extra_args)
            cmd_list += _parse_env_options(command)
            return _run_external(cmd_list, sequence)
        except ValueError as exc:  # pragma: no cover - invalid options
            raise ValueError(
                f"Invalid GENECODER_{command.upper()}_OPTIONS: {exc}"
            ) from exc
        except (RuntimeError, subprocess.CalledProcessError) as exc:  # pragma: no cover - error path
            logger.warning(
                "%s failed: %s; falling back to simple error model",
                command,
                exc,
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
    sequence: str,
    error_rate: float = 0.05,
    rng: random.Random | None = None,
    profile: str | None = None,
) -> str:
    """Use ``dnarsim`` if available, else fall back to :func:`simulate_errors`.

    ``rng`` is forwarded to :func:`simulate_errors` if the external command is
    unavailable.
    """


    if rng is None:
        rng = make_rng()

    extra = ["-p", profile] if profile else None
    return _simulate_adapter("dnarsim", sequence, error_rate, rng, extra)


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
    """Return ``sequence`` processed by the named simulator.

    .. deprecated:: 0.2
       Use :func:`genecoder.simulators.simulate_reads` instead.
    """

    import warnings

    warnings.warn(
        "genecoder.nanopore_sim.simulate_reads is deprecated; use genecoder.simulators.simulate_reads",
        DeprecationWarning,
        stacklevel=2,
    )

    from .simulators import simulate_reads as _simulate_reads

    return _simulate_reads(sequence, simulator, error_rate=error_rate)


class Channel(Simulator):
    """Adapter implementing :class:`BaseChannel` for built-in simulators."""

    def __init__(self, name: str, error_rate: float = 0.05) -> None:
        self.name = name
        self.error_rate = error_rate

    def simulate(self, sequence: str) -> str:
        adapter = SIMULATOR_ADAPTERS[self.name]
        return adapter(sequence, self.error_rate, make_rng())



def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    """Register the builtin simulators."""

    for name in SIMULATOR_ADAPTERS:
        registrar(name, Channel(name))


