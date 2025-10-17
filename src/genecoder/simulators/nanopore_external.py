"""External simulator adapters used by the Nanopore channels."""

from __future__ import annotations

import logging
import random
import shutil
import subprocess
from typing import Callable

try:  # Optional at runtime
    from numba import njit
except Exception:  # pragma: no cover - fallback when numba missing
    from typing import Callable as _Callable, ParamSpec, TypeVar

    P = ParamSpec("P")
    R = TypeVar("R")

    def njit(*args: object, **kwargs: object) -> _Callable[[ _Callable[P, R]], _Callable[P, R]]:
        def wrapper(func: _Callable[P, R]) -> _Callable[P, R]:
            return func

        return wrapper

from ..error_simulation import NUCLEOTIDES, _random_substitution
from ..simulator_utils import _parse_env_options, _run_external

__all__ = [
    "simulate_simple_model",
    "run_dnarsim_cli",
]


@njit(cache=True, forceobj=True)  # type: ignore[misc]
def simulate_simple_model(sequence: str, error_rate: float, rng: random.Random) -> str:
    """Fallback Nanopore simulator used when external tools are unavailable."""

    sub_p = error_rate * 0.4
    ins_p = error_rate * 0.3
    base_del_p = error_rate * 0.3

    mutated: list[str] = []
    prev = ""
    run_len = 0
    for nt in sequence:
        if nt == prev:
            run_len += 1
        else:
            run_len = 1
            prev = nt

        del_p = base_del_p * (2 if run_len >= 5 else 1)
        del_p = min(1.0, del_p)
        if rng.random() < del_p:
            continue

        if rng.random() < sub_p:
            nt = _random_substitution(nt, rng)

        mutated.append(nt)
        if rng.random() < ins_p:
            mutated.append(rng.choice(NUCLEOTIDES))

    return "".join(mutated)


def run_dnarsim_cli(
    sequence: str,
    error_rate: float,
    profile: str | None,
    *,
    logger: Callable[[str], None] | None = None,
) -> str:
    """Invoke the external ``dnarsim`` binary and return the simulated read."""

    cmd = "dnarsim"
    if shutil.which(cmd):
        cmd_list = [cmd, "-e", str(error_rate)]
        if profile:
            cmd_list += ["-p", profile]
        try:
            cmd_list += _parse_env_options(cmd)
            return _run_external(cmd_list, sequence)
        except (ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
            log = logging.getLogger(__name__).warning if logger is None else logger
            log(f"{cmd} failed: {exc}; falling back to simple dnarsim model")
    else:
        log = logging.getLogger(__name__).warning if logger is None else logger
        log(f"{cmd} not found; falling back to simple dnarsim model")
    raise RuntimeError("fallback")

