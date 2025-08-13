"""Wrapper for optional nanopore read simulators."""
from __future__ import annotations

import random
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Callable, Sequence

from .simulator_utils import _parse_env_options, _run_external

__all__ = [
    "simulate_d2sim",
    "simulate_dnarsim",
    "simulate_squigulator",
    "simulate_desp",
    "simulate_reads",
    "Channel",
    "DNARSIM_RATE_TABLES",
]

from .api import Simulator
from .simulators import register_simulator as _register_simulator

logger = logging.getLogger(__name__)

from .random_utils import make_rng
from .error_simulation import simulate_errors


try:  # pragma: no cover - optional dependency
    import yaml

    _rates_path = Path(__file__).resolve().parents[2] / "configs" / "dnarsim_rates.yaml"
    with open(_rates_path, "r", encoding="utf-8") as _fh:
        _rates_data = yaml.safe_load(_fh) or {}
    if isinstance(_rates_data, dict):
        DNARSIM_RATE_TABLES: dict[str, dict[str, float]] = {
            str(name): {
                "substitution_rate": float(tbl.get("substitution_rate", 0.0)),
                "insertion_rate": float(tbl.get("insertion_rate", 0.0)),
                "deletion_rate": float(tbl.get("deletion_rate", 0.0)),
            }
            for name, tbl in _rates_data.items()
            if isinstance(tbl, dict)
        }
    else:  # pragma: no cover - unexpected structure
        DNARSIM_RATE_TABLES = {}
except Exception:  # pragma: no cover - fallback when yaml missing
    DNARSIM_RATE_TABLES = {}


def _simulate_homopolymer_errors(
    sequence: str,
    substitution_prob: float = 0.0,
    insertion_prob: float = 0.0,
    deletion_prob: float = 0.0,
    rng: random.Random | None = None,
) -> str:
    """Simulate errors with indel rates weighted by homopolymer length."""

    if rng is None:
        rng = make_rng()

    if insertion_prob == 0.0 and deletion_prob == 0.0:
        try:
            return simulate_errors(sequence, substitution_prob, rng=rng)
        except TypeError:
            return simulate_errors(
                sequence, substitution_prob=substitution_prob, rng=rng
            )

    mutated: list[str] = []
    i = 0
    seq_len = len(sequence)
    while i < seq_len:
        nt = sequence[i]
        j = i + 1
        while j < seq_len and sequence[j] == nt:
            j += 1
        run_len = j - i
        factor = run_len / 4.0 if run_len >= 4 else 1.0
        ins_p = min(1.0, insertion_prob * factor)
        del_p = min(1.0, deletion_prob * factor)
        run_seq = sequence[i:j]
        try:
            mutated.append(
                simulate_errors(
                    run_seq,
                    substitution_prob,
                    ins_p,
                    del_p,
                    rng=rng,
                )
            )
        except TypeError:
            mutated.append(
                simulate_errors(
                    run_seq, substitution_prob=substitution_prob, rng=rng
                )
            )
        i = j
    return "".join(mutated)


def _simulate_adapter(
    command: str,
    sequence: str,
    error_rate: float,
    rng: random.Random | None,
    extra_args: Sequence[str] | None = None,
    rate_table: dict[str, float] | None = None,
) -> str:

    """Return ``sequence`` processed by an external ``command`` if available."""
    if shutil.which(command):
        try:
            cmd_list = [command]
            if command in {"d2sim", "dnarsim", "squigulator", "desp"}:
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
    if rate_table:
        return _simulate_homopolymer_errors(
            sequence,
            rate_table.get("substitution_rate", 0.0),
            rate_table.get("insertion_rate", 0.0),
            rate_table.get("deletion_rate", 0.0),
            rng,
        )
    try:
        return _simulate_homopolymer_errors(sequence, error_rate, rng=rng)
    except TypeError:
        return _simulate_homopolymer_errors(
            sequence, substitution_prob=error_rate, rng=rng
        )



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
    rate_table = DNARSIM_RATE_TABLES.get(profile) if profile else None
    return _simulate_adapter("dnarsim", sequence, error_rate, rng, extra, rate_table)


def simulate_squigulator(
    sequence: str, error_rate: float = 0.05, rng: random.Random | None = None
) -> str:
    """Use ``squigulator`` if available, else fall back to :func:`simulate_errors`.


    ``rng`` provides the randomness source for the fallback simulator.
    """


    if rng is None:
        rng = make_rng()

    return _simulate_adapter("squigulator", sequence, error_rate, rng)


def simulate_desp(
    sequence: str, error_rate: float = 0.05, rng: random.Random | None = None
) -> str:
    """Use ``desp`` if available, else fall back to :func:`simulate_errors`."""

    if rng is None:
        rng = make_rng()

    return _simulate_adapter("desp", sequence, error_rate, rng)


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
    "desp": simulate_desp,
    # backward compatibility names
    "nanopore": simulate_d2sim,
    "none": simulate_none,
}


def simulate_reads(
    sequence: str,
    simulator: str,
    error_rate: float = 0.05,
    profile: str | None = None,
) -> str:
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

    return _simulate_reads(
        sequence, simulator, error_rate=error_rate, profile=profile
    )


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


