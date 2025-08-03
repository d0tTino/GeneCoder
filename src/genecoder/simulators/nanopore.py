"""Wrapper for the optional d2sim nanopore simulator."""
from __future__ import annotations

from typing import Callable, Sequence, Dict, Iterable
import random
import shutil
import subprocess
import logging
from pathlib import Path

try:  # Optional at runtime
    from numba import njit
except Exception:  # pragma: no cover - fallback when numba missing
    from typing import Callable, TypeVar, ParamSpec

    P = ParamSpec("P")
    R = TypeVar("R")

    def njit(*args: object, **kwargs: object) -> Callable[[Callable[P, R]], Callable[P, R]]:
        def wrapper(func: Callable[P, R]) -> Callable[P, R]:
            return func

        return wrapper

from ..random_utils import make_rng
from ..nanopore_sim import (
    simulate_d2sim,
    simulate_desp,
    _run_external,
    _parse_env_options,
)
from ..api import Simulator
from .base import BaseChannel
from ..error_simulation import (
    _random_substitution,
    NUCLEOTIDES,
)
from . import register_simulator as _register_simulator

__all__ = [
    "NanoporeChannel",
    "NanoporeDeSPChannel",
    "NanoporeDNArSimChannel",
    "register",
    "NANOPORE_PROFILES",
]

# Preset parameter profiles for :class:`NanoporeChannel` loaded from YAML.
_DEFAULT_NANOPORE_PROFILES: dict[
    str, dict[str, float | int | Dict[int, float]]
] = {
    "minion": {
        "error_rate": 0.12,
        "substitution_rate": 0.02,
        "insertion_rate": 0.04,
        "deletion_rate": 0.06,
    },
    "promethion": {
        "error_rate": 0.08,
        "substitution_rate": 0.015,
        "insertion_rate": 0.02,
        "deletion_rate": 0.045,
    },
    "r10": {
        "error_rate": 0.05,
        "substitution_rate": 0.01,
        "insertion_rate": 0.02,
        "deletion_rate": 0.03,
    },
}

try:  # pragma: no cover - optional dependency
    import yaml

    _cfg_path = Path(__file__).resolve().parents[3] / "configs" / "nanopore.yml"
    with open(_cfg_path, "r", encoding="utf-8") as _fh:
        _data = yaml.safe_load(_fh) or {}
    if isinstance(_data, dict):
        NANOPORE_PROFILES: dict[
            str, dict[str, float | int | Dict[int, float]]
        ] = {
            str(name): params
            for name, params in _data.items()
            if isinstance(params, dict)
        }
    else:  # pragma: no cover - unexpected structure
        NANOPORE_PROFILES = _DEFAULT_NANOPORE_PROFILES
except Exception:  # pragma: no cover - fallback when yaml missing
    NANOPORE_PROFILES = _DEFAULT_NANOPORE_PROFILES


@njit(cache=True, forceobj=True)  # type: ignore[misc]
def _simulate_fallback_jit(sequence: str, error_rate: float, rng: random.Random) -> str:
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


@njit(cache=True, forceobj=True)  # type: ignore[misc]
def _mutate_read_jit(
    read: str,
    quality: Sequence[float] | None,
    rng: random.Random,
    substitution_rate: float,
    insertion_rate: float,
    deletion_rate: float,
    context_errors: Dict[str, float],
    insertion_profile: Dict[int, float],
    deletion_profile: Dict[int, float],
) -> str:
    mutated = []
    prev = ""
    run_len = 0
    for idx, nt in enumerate(read):
        if nt == prev:
            run_len += 1
        else:
            run_len = 1
            prev = nt

        del_rate = deletion_profile.get(run_len, deletion_rate)
        del_rate = min(1.0, del_rate)
        if rng.random() < del_rate:
            continue

        sub_rate = (
            quality[idx] if quality is not None and idx < len(quality) else substitution_rate
        )
        if context_errors and idx > 0:
            ctx = read[idx - 1 : idx + 1].upper()
            sub_rate *= context_errors.get(ctx, 1.0)

        if rng.random() < sub_rate:
            nt = _random_substitution(nt, rng)

        mutated.append(nt)
        ins_rate = insertion_profile.get(run_len, insertion_rate)
        if rng.random() < ins_rate:
            mutated.append(rng.choice(NUCLEOTIDES))

    return "".join(mutated)


class NanoporeChannel(BaseChannel):
    """Channel that delegates to :mod:`d2sim` if installed."""

    def __init__(
        self,
        error_rate: float = 0.05,
        *,
        substitution_rate: float = 0.0,
        insertion_rate: float = 0.0,
        deletion_rate: float = 0.0,
        coverage: int = 1,
        quality_profile: Sequence[float] | None = None,
        context_errors: Dict[str, float] | None = None,
        insertion_profile: Dict[int, float] | None = None,
        deletion_profile: Dict[int, float] | None = None,
        profile_path: str | None = None,
    ) -> None:
        if profile_path is not None:
            try:
                import yaml
            except Exception:  # pragma: no cover - optional dependency
                from genecoder.plugin_manager import yaml as yaml_module
                if yaml_module is None:
                    raise
                yaml = yaml_module

            with open(profile_path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            if not isinstance(data, dict):
                raise ValueError("Profile file must map keys to values")
            error_rate = float(data.get("error_rate", error_rate))
            substitution_rate = float(data.get("substitution_rate", substitution_rate))
            insertion_rate = float(data.get("insertion_rate", insertion_rate))
            deletion_rate = float(data.get("deletion_rate", deletion_rate))
            coverage = int(data.get("coverage", coverage))
            quality_profile = data.get("quality_profile", quality_profile)
            context_errors = data.get("context_errors", context_errors)
            insertion_profile = data.get("insertion_profile", insertion_profile)
            deletion_profile = data.get("deletion_profile", deletion_profile)

        super().__init__(
            substitution_rate=substitution_rate,
            insertion_rate=insertion_rate,
            deletion_rate=deletion_rate,
            coverage=coverage,
        )
        self.error_rate = error_rate
        self.quality_profile = (
            tuple(quality_profile) if quality_profile is not None else None
        )
        self.context_errors = {
            k.upper(): float(v) for k, v in (context_errors or {}).items()
        }
        self.insertion_profile = {
            int(k): float(v) for k, v in (insertion_profile or {}).items()
        }
        self.deletion_profile = {
            int(k): float(v) for k, v in (deletion_profile or {}).items()
        }

    def simulate(self, sequence: str) -> str:
        rng = make_rng()
        quality = self.quality_profile
        coverage = max(1, self.get_coverage(sequence))
        reads = [
            _mutate_read(
                simulate_d2sim(sequence, error_rate=self.error_rate, rng=rng),
                quality,
                rng,
                self,
            )
            for _ in range(coverage)
        ]
        if coverage == 1:
            return reads[0]
        return _consensus(reads)


class NanoporeDeSPChannel(NanoporeChannel):
    """Channel wrapper using the external ``desp`` simulator."""

    def simulate(self, sequence: str) -> str:
        rng = make_rng()
        quality = self.quality_profile
        coverage = max(1, self.get_coverage(sequence))
        reads = [
            _mutate_read(
                simulate_desp(sequence, error_rate=self.error_rate, rng=rng),
                quality,
                rng,
                self,
            )
            for _ in range(coverage)
        ]
        if coverage == 1:
            return reads[0]
        return _consensus(reads)


class NanoporeDNArSimChannel(NanoporeChannel):
    """Channel wrapper using the external ``dnarsim`` simulator."""

    def __init__(
        self,
        error_rate: float = 0.05,
        profile: str | None = None,
        *,
        substitution_rate: float = 0.0,
        insertion_rate: float = 0.0,
        deletion_rate: float = 0.0,
        coverage: int = 1,
        quality_profile: Sequence[float] | None = None,
        context_errors: Dict[str, float] | None = None,
    ) -> None:
        super().__init__(
            error_rate,
            substitution_rate=substitution_rate,
            insertion_rate=insertion_rate,
            deletion_rate=deletion_rate,
            coverage=coverage,
            quality_profile=quality_profile,
            context_errors=context_errors,
        )
        self.profile = profile

    def _simulate_cli(self, sequence: str) -> str:
        cmd = "dnarsim"
        if shutil.which(cmd):
            cmd_list = [cmd, "-e", str(self.error_rate)]
            if self.profile:
                cmd_list += ["-p", self.profile]
            try:
                cmd_list += _parse_env_options(cmd)
                return _run_external(cmd_list, sequence)
            except (ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
                logging.getLogger(__name__).warning(
                    "%s failed: %s; falling back to simple dnarsim model", cmd, exc
                )
        else:
            logging.getLogger(__name__).warning(
                "%s not found; falling back to simple dnarsim model", cmd
            )
        raise RuntimeError("fallback")

    @staticmethod
    def _simulate_fallback(sequence: str, error_rate: float, rng: random.Random) -> str:
        from typing import cast

        return cast(str, _simulate_fallback_jit(sequence, error_rate, rng))


    def simulate(self, sequence: str) -> str:
        rng = make_rng()
        quality = self.quality_profile
        coverage = max(1, self.get_coverage(sequence))

        reads = []
        for _ in range(coverage):
            try:
                base = self._simulate_cli(sequence)
            except Exception:
                base = self._simulate_fallback(sequence, self.error_rate, rng)
            reads.append(_mutate_read(base, quality, rng, self))

        if coverage == 1:
            return reads[0]
        return _consensus(reads)


def _mutate_read(
    read: str, quality: Sequence[float] | None, rng: random.Random, channel: NanoporeChannel
) -> str:
    from typing import cast

    return cast(
        str,
        _mutate_read_jit(
            read,
            quality,
            rng,
            channel.substitution_rate,
            channel.insertion_rate,
            channel.deletion_rate,
            channel.context_errors,
            channel.insertion_profile,
            channel.deletion_profile,
        ),
    )


def _consensus(reads: Iterable[str]) -> str:
    reads = list(reads)
    if not reads:
        return ""
    length = max(len(r) for r in reads)
    result = []
    for i in range(length):
        counts: Dict[str, int] = {}
        for r in reads:
            if i < len(r):
                base = r[i]
                counts[base] = counts.get(base, 0) + 1
        if counts:
            result.append(max(counts, key=lambda k: counts[k]))
    return "".join(result)


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    registrar("nanopore_d2sim", NanoporeChannel())
    registrar("nanopore_desp", NanoporeDeSPChannel())
    registrar("nanopore_dnarsim", NanoporeDNArSimChannel())

