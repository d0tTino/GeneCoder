"""Wrapper for the optional d2sim nanopore simulator."""
from __future__ import annotations

from typing import Any, Callable, Sequence, Dict, Iterable, Mapping, cast
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
from ..nanopore_sim import simulate_d2sim, simulate_desp, DNARSIM_RATE_TABLES as _DNARSIM_RATE_TABLES
from ..simulator_utils import _run_external, _parse_env_options
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
    "DNARSIM_RATE_TABLES",
]

# ---------------------------------------------------------------------------
# Validation helpers


def _validate_rate(name: str, rate: float | int) -> float:
    try:
        value = float(rate)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number between 0 and 1") from None
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return value


def _validate_indel_profile(
    profile: Mapping[int, float] | None, name: str
) -> Dict[int, float]:
    validated: Dict[int, float] = {}
    for run_len, prob in (profile or {}).items():
        try:
            rl = int(run_len)
        except (TypeError, ValueError):
            raise ValueError(f"{name} run lengths must be integers") from None
        validated[rl] = _validate_rate(f"{name}[{rl}]", prob)
    return validated


def _validate_context_profiles(
    profiles: Mapping[str, Mapping[int, float]] | None, name: str
) -> Dict[str, Dict[int, float]]:
    validated: Dict[str, Dict[int, float]] = {}
    for ctx, prof in (profiles or {}).items():
        if not isinstance(prof, Mapping):
            raise ValueError(
                f"{name}[{ctx}] must be a mapping of run lengths to probabilities"
            )
        validated[str(ctx).upper()] = _validate_indel_profile(prof, f"{name}[{ctx}]")
    return validated

# ---------------------------------------------------------------------------
# Preset parameter profiles for :class:`NanoporeChannel` loaded from YAML.
_DEFAULT_NANOPORE_PROFILES: dict[
    str, dict[str, float | int | Dict[int, float] | Dict[str, Dict[int, float]]]
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

    _cfg_dir = Path(__file__).resolve().parents[3] / "configs"
    with open(_cfg_dir / "nanopore.yml", "r", encoding="utf-8") as _fh:
        _data = yaml.safe_load(_fh) or {}

    def _parse_profile(params: dict[str, Any]) -> dict[str, Any]:
        parsed: dict[str, Any] = {}
        for key, value in params.items():
            if key in {"insertion_profile", "deletion_profile"}:
                prof = value if isinstance(value, Mapping) else None
                parsed[key] = _validate_indel_profile(prof, key)
            elif key in {"context_insertions", "context_deletions"}:
                prof = value if isinstance(value, Mapping) else None
                parsed[key] = _validate_context_profiles(prof, key)
            else:
                parsed[key] = value
        return parsed

    if isinstance(_data, dict):
        NANOPORE_PROFILES: dict[str, dict[str, Any]] = {
            str(name): _parse_profile(params)
            for name, params in _data.items()
            if isinstance(params, dict)
        }
    else:  # pragma: no cover - unexpected structure
        NANOPORE_PROFILES = _DEFAULT_NANOPORE_PROFILES

    NANOPORE_PROFILES.update(_DNARSIM_RATE_TABLES)
    DNARSIM_RATE_TABLES = _DNARSIM_RATE_TABLES
except Exception:  # pragma: no cover - fallback when yaml missing
    NANOPORE_PROFILES = _DEFAULT_NANOPORE_PROFILES
    DNARSIM_RATE_TABLES = {}


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
    context_insertions: Dict[str, Dict[int, float]],
    context_deletions: Dict[str, Dict[int, float]],
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

        ctx = read[idx - 1 : idx + 1].upper() if idx > 0 else ""

        del_rate = deletion_profile.get(run_len, deletion_rate)
        if context_deletions and ctx:
            ctx_profile = context_deletions.get(ctx)
            if ctx_profile is not None:
                del_rate = ctx_profile.get(run_len, ctx_profile.get(1, del_rate))
        del_rate = min(1.0, del_rate)
        if rng.random() < del_rate:
            continue

        sub_rate = (
            quality[idx] if quality is not None and idx < len(quality) else substitution_rate
        )
        if context_errors and ctx:
            sub_rate *= context_errors.get(ctx, 1.0)

        if rng.random() < sub_rate:
            nt = _random_substitution(nt, rng)

        mutated.append(nt)
        ins_rate = insertion_profile.get(run_len, insertion_rate)
        if context_insertions and ctx:
            ctx_profile = context_insertions.get(ctx)
            if ctx_profile is not None:
                ins_rate = ctx_profile.get(run_len, ctx_profile.get(1, ins_rate))
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
        context_insertions: Dict[str, Dict[int, float]] | None = None,
        context_deletions: Dict[str, Dict[int, float]] | None = None,
        insertion_profile: Dict[int, float] | None = None,
        deletion_profile: Dict[int, float] | None = None,
        profile: str | None = None,
        profile_path: str | None = None,
    ) -> None:
        if profile is not None:
            params = NANOPORE_PROFILES.get(profile.lower())
            if params is not None:
                error_rate = float(cast(float | int, params.get("error_rate", error_rate)))
                substitution_rate = float(
                    cast(float | int, params.get("substitution_rate", substitution_rate))
                )
                insertion_rate = float(
                    cast(float | int, params.get("insertion_rate", insertion_rate))
                )
                deletion_rate = float(
                    cast(float | int, params.get("deletion_rate", deletion_rate))
                )
                coverage = int(cast(float | int, params.get("coverage", coverage)))
                quality_profile = cast(
                    Sequence[float] | None,
                    params.get("quality_profile", quality_profile),
                )
                context_errors = cast(
                    Dict[str, float] | None,
                    params.get("context_errors", context_errors),
                )
                context_insertions = cast(
                    Dict[str, Dict[int, float]] | None,
                    params.get("context_insertions", context_insertions),
                )
                context_deletions = cast(
                    Dict[str, Dict[int, float]] | None,
                    params.get("context_deletions", context_deletions),
                )
                insertion_profile = cast(
                    Dict[int, float] | None,
                    params.get("insertion_profile", insertion_profile),
                )
                deletion_profile = cast(
                    Dict[int, float] | None,
                    params.get("deletion_profile", deletion_profile),
                )
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
            context_insertions = data.get("context_insertions", context_insertions)
            context_deletions = data.get("context_deletions", context_deletions)
            insertion_profile = data.get("insertion_profile", insertion_profile)
            deletion_profile = data.get("deletion_profile", deletion_profile)
        error_rate = _validate_rate("error_rate", error_rate)
        substitution_rate = _validate_rate("substitution_rate", substitution_rate)
        insertion_rate = _validate_rate("insertion_rate", insertion_rate)
        deletion_rate = _validate_rate("deletion_rate", deletion_rate)

        context_insertions = _validate_context_profiles(
            context_insertions, "context_insertions"
        )
        context_deletions = _validate_context_profiles(
            context_deletions, "context_deletions"
        )
        insertion_profile = _validate_indel_profile(
            insertion_profile, "insertion_profile"
        )
        deletion_profile = _validate_indel_profile(
            deletion_profile, "deletion_profile"
        )

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
        self.context_insertions = context_insertions
        self.context_deletions = context_deletions
        self.insertion_profile = insertion_profile
        self.deletion_profile = deletion_profile

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

    def with_profile(self, profile: str) -> "NanoporeChannel":
        """Return a new channel configured to use ``profile``.

        Unknown profiles leave the channel unchanged.
        """

        if profile.lower() not in NANOPORE_PROFILES:
            return self
        return type(self)(
            profile=profile,
            quality_profile=self.quality_profile,
            context_errors=dict(self.context_errors),
            context_insertions=self.context_insertions,
            context_deletions=self.context_deletions,
            insertion_profile=self.insertion_profile,
            deletion_profile=self.deletion_profile,
        )


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
        context_insertions: Dict[str, Dict[int, float]] | None = None,
        context_deletions: Dict[str, Dict[int, float]] | None = None,
    ) -> None:
        super().__init__(
            error_rate,
            substitution_rate=substitution_rate,
            insertion_rate=insertion_rate,
            deletion_rate=deletion_rate,
            coverage=coverage,
            quality_profile=quality_profile,
            context_errors=context_errors,
            context_insertions=context_insertions,
            context_deletions=context_deletions,
            profile=profile,
        )
        self.profile = profile
        self._profile_rates: dict[str, float] = (
            DNARSIM_RATE_TABLES.get(profile, {}) if profile else {}
        )

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

    def with_profile(self, profile: str) -> "NanoporeDNArSimChannel":
        """Return a new channel configured to use ``profile``."""
        return type(self)(
            self.error_rate,
            profile,
            coverage=self.coverage,
            quality_profile=self.quality_profile,
            context_errors=self.context_errors,
            context_insertions=self.context_insertions,
            context_deletions=self.context_deletions,
        )

    @staticmethod
    def _simulate_fallback(sequence: str, error_rate: float, rng: random.Random) -> str:
        from typing import cast

        return cast(str, _simulate_fallback_jit(sequence, error_rate, rng))


    def simulate(self, sequence: str) -> str:
        from typing import cast

        rng = make_rng()
        quality = self.quality_profile
        coverage = max(1, self.get_coverage(sequence))

        reads = []
        for _ in range(coverage):
            try:
                base = self._simulate_cli(sequence)
                sub = self.substitution_rate
                ins = self.insertion_rate
                dele = self.deletion_rate
            except Exception:
                base = self._simulate_fallback(sequence, self.error_rate, rng)
                rates = self._profile_rates
                sub = rates.get("substitution_rate", self.substitution_rate)
                ins = rates.get("insertion_rate", self.insertion_rate)
                dele = rates.get("deletion_rate", self.deletion_rate)
            reads.append(
                cast(
                    str,
                    _mutate_read_jit(
                        base,
                        quality,
                        rng,
                        sub,
                        ins,
                        dele,
                        self.context_errors,
                        self.insertion_profile,
                        self.deletion_profile,
                        self.context_insertions,
                        self.context_deletions,
                    ),
                )
            )

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
            channel.context_insertions,
            channel.context_deletions,
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

