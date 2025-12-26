"""Wrapper for the optional d2sim nanopore simulator."""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Mapping, Sequence, cast
from copy import deepcopy
from types import ModuleType
import json
import random
from pathlib import Path

from ..random_utils import make_rng
from ..d2sim_adapter import simulate_d2sim
from ..desp_adapter import simulate_desp
from ..api import Simulator
from ..formats import SequenceBatch
from . import register_simulator as _register_simulator
from .base import BaseChannel
from .batch_utils import load_coverage_distribution
from .nanopore_batch import (
    mutate_read as _mutate_read,
    mutate_read_jit as _mutate_read_jit,
    consensus as _consensus,
    simulate_batch as _simulate_batch_impl,
)
from .nanopore_external import run_dnarsim_cli, simulate_simple_model as _simulate_fallback_jit
from .nanopore_profiles import (
    BASE_PROFILE_KEYS as _BASE_PROFILE_KEYS,
    load_yaml_data as _load_yaml_data,
    merge_profiles as _merge_profiles,
    parse_context_overrides as _parse_context_overrides,
    parse_profile as _parse_profile,
    parse_rate_table as _parse_rate_table,
    split_context_indels as _split_context_indels,
    validate_context_profiles as _validate_context_profiles,
    validate_indel_profile as _validate_indel_profile,
    validate_rate as _validate_rate,
)

__all__ = [
    "NanoporeChannel",
    "NanoporeDeSPChannel",
    "NanoporeDNArSimChannel",
    "load_coverage_distribution",
    "register",
    "NANOPORE_PROFILES",
    "DNARSIM_RATE_TABLES",
]

# ---------------------------------------------------------------------------
# Preset parameter profiles for :class:`NanoporeChannel` loaded from YAML.

_FALLBACK_PROFILE_DATA: dict[
    str, dict[str, float | int | Dict[int, float] | Dict[str, Dict[int, float]]]
] = {
    "minion": {
        "error_rate": 0.13,
        "substitution_rate": 0.019,
        "insertion_rate": 0.046,
        "deletion_rate": 0.065,
        "coverage": 30,
        "insertion_profile": {5: 0.16},
        "deletion_profile": {5: 0.22},
        "context_insertions": {
            "AA": {1: 0.05, 5: 0.24},
            "TT": {1: 0.05, 5: 0.24},
            "GG": {1: 0.03, 5: 0.14},
            "CC": {1: 0.03, 5: 0.14},
        },
        "context_deletions": {
            "AA": {1: 0.08, 5: 0.26},
            "TT": {1: 0.08, 5: 0.26},
            "GG": {1: 0.04, 5: 0.18},
            "CC": {1: 0.04, 5: 0.18},
        },
    },
    "promethion": {
        "error_rate": 0.08,
        "substitution_rate": 0.015,
        "insertion_rate": 0.02,
        "deletion_rate": 0.045,
        "coverage": 30,
        "insertion_profile": {5: 0.11},
        "deletion_profile": {5: 0.16},
        "context_insertions": {
            "AA": {1: 0.04, 5: 0.18},
            "TT": {1: 0.04, 5: 0.18},
            "GG": {1: 0.02, 5: 0.09},
            "CC": {1: 0.02, 5: 0.09},
        },
        "context_deletions": {
            "AA": {1: 0.06, 5: 0.2},
            "TT": {1: 0.06, 5: 0.2},
            "GG": {1: 0.03, 5: 0.12},
            "CC": {1: 0.03, 5: 0.12},
        },
    },
    "r10": {
        "error_rate": 0.05,
        "substitution_rate": 0.01,
        "insertion_rate": 0.015,
        "deletion_rate": 0.025,
        "coverage": 30,
        "insertion_profile": {5: 0.08},
        "deletion_profile": {5: 0.12},
        "context_insertions": {
            "AA": {1: 0.03, 5: 0.12},
            "TT": {1: 0.03, 5: 0.12},
            "GG": {1: 0.015, 5: 0.06},
            "CC": {1: 0.015, 5: 0.06},
        },
        "context_deletions": {
            "AA": {1: 0.05, 5: 0.14},
            "TT": {1: 0.05, 5: 0.14},
            "GG": {1: 0.025, 5: 0.09},
            "CC": {1: 0.025, 5: 0.09},
        },
    },
}

# ---------------------------------------------------------------------------
# Profile configuration helpers


def _load_profiles_from_directory(
    cfg_dir: Path, yaml_module: ModuleType | None = None
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if yaml_module is None:
        import yaml as yaml_module  # type: ignore[import]

    profiles: dict[str, dict[str, Any]] = {
        str(name).lower(): deepcopy(params)
        for name, params in _FALLBACK_PROFILE_DATA.items()
    }

    base_path = cfg_dir / "nanopore.yml"
    try:
        with open(base_path, "r", encoding="utf-8") as fh:
            base_data = _load_yaml_data(fh.read(), yaml_module) or {}
    except FileNotFoundError:
        base_data = {}
    if isinstance(base_data, Mapping):
        for name, params in base_data.items():
            if isinstance(params, Mapping):
                key = str(name).lower()
                parsed = _parse_profile(params)
                existing = profiles.get(key, {})
                profiles[key] = _merge_profiles(existing, parsed)

    context_defaults: dict[str, Mapping[str, Any]] = {}
    for name, params in _FALLBACK_PROFILE_DATA.items():
        ctx = {
            key: value
            for key, value in params.items()
            if key in {
                "insertion_profile",
                "deletion_profile",
                "context_insertions",
                "context_deletions",
                "context_indels",
            }
        }
        if ctx:
            context_defaults[str(name).lower()] = ctx

    context_path = cfg_dir / "nanopore_context.yaml"
    try:
        with open(context_path, "r", encoding="utf-8") as fh:
            context_data = _load_yaml_data(fh.read(), yaml_module) or {}
    except FileNotFoundError:
        context_data = {}
    if not isinstance(context_data, Mapping):
        context_data = {}
    context_defaults.update({
        str(name).lower(): params
        for name, params in context_data.items()
        if isinstance(params, Mapping)
    })

    for name, params in context_defaults.items():
        parsed = _parse_context_overrides(params, f"context profile {name}")
        existing = profiles.get(name, {})
        profiles[name] = _merge_profiles(existing, parsed)

    rates_path = cfg_dir / "dnarsim_rates.yaml"
    try:
        with open(rates_path, "r", encoding="utf-8") as fh:
            rates_data = _load_yaml_data(fh.read(), yaml_module) or {}
    except FileNotFoundError:
        rates_data = {}

    dnarsim_tables: dict[str, dict[str, Any]] = {}
    if isinstance(rates_data, Mapping):
        for name, tbl in rates_data.items():
            if isinstance(tbl, Mapping):
                dnarsim_tables[str(name)] = _parse_rate_table(tbl)

    combined = {
        key: deepcopy(params) for key, params in profiles.items()
    }
    for name, table in dnarsim_tables.items():
        combined[str(name).lower()] = deepcopy(table)

    return combined, dnarsim_tables


try:  # pragma: no cover - optional dependency
    import yaml

    _cfg_dir = Path(__file__).resolve().parents[3] / "configs"
    NANOPORE_PROFILES, DNARSIM_RATE_TABLES = _load_profiles_from_directory(
        _cfg_dir, yaml
    )
except Exception:  # pragma: no cover - fallback when yaml missing
    NANOPORE_PROFILES = {
        key: deepcopy(params) for key, params in _FALLBACK_PROFILE_DATA.items()
    }
    DNARSIM_RATE_TABLES = {}


class NanoporeChannel(BaseChannel):
    """Channel that delegates to :mod:`d2sim` if installed."""

    supports_batches = True

    def __init__(
        self,
        error_rate: float = 0.05,
        *,
        substitution_rate: float = 0.0,
        insertion_rate: float = 0.0,
        deletion_rate: float = 0.0,
        coverage: float = 1,
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
                coverage = float(cast(float | int, params.get("coverage", coverage)))
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
                data = _load_yaml_data(fh.read(), yaml) or {}
            if not isinstance(data, dict):
                raise ValueError("Profile file must map keys to values")
            error_rate = float(data.get("error_rate", error_rate))
            substitution_rate = float(data.get("substitution_rate", substitution_rate))
            insertion_rate = float(data.get("insertion_rate", insertion_rate))
            deletion_rate = float(data.get("deletion_rate", deletion_rate))
            coverage = float(data.get("coverage", coverage))
            quality_profile = data.get("quality_profile", quality_profile)
            context_errors = data.get("context_errors", context_errors)

            if "context_insertions" in data:
                ci = data["context_insertions"]
                if not isinstance(ci, Mapping):
                    raise ValueError("context_insertions must be a mapping")
                base = {
                    k: dict(v) for k, v in (context_insertions or {}).items()
                }
                for ctx, prof in ci.items():
                    if not isinstance(prof, Mapping):
                        raise ValueError(
                            f"context_insertions[{ctx}] must map run lengths to rates"
                        )
                    base.setdefault(str(ctx).upper(), {}).update(prof)
                context_insertions = base
            if "context_deletions" in data:
                cd = data["context_deletions"]
                if not isinstance(cd, Mapping):
                    raise ValueError("context_deletions must be a mapping")
                base = {
                    k: dict(v) for k, v in (context_deletions or {}).items()
                }
                for ctx, prof in cd.items():
                    if not isinstance(prof, Mapping):
                        raise ValueError(
                            f"context_deletions[{ctx}] must map run lengths to rates"
                        )
                    base.setdefault(str(ctx).upper(), {}).update(prof)
                context_deletions = base

            if "context_indels" in data:
                ctx_ins, ctx_del = _split_context_indels(
                    data.get("context_indels"), "context_indels"
                )
                if ctx_ins:
                    base = {
                        k: dict(v) for k, v in (context_insertions or {}).items()
                    }
                    for ctx, prof in ctx_ins.items():
                        base.setdefault(ctx, {}).update(prof)
                    context_insertions = base
                if ctx_del:
                    base = {
                        k: dict(v) for k, v in (context_deletions or {}).items()
                    }
                    for ctx, prof in ctx_del.items():
                        base.setdefault(ctx, {}).update(prof)
                    context_deletions = base
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

    def simulate(self, sequence: str | SequenceBatch) -> str | SequenceBatch:
        if isinstance(sequence, SequenceBatch):
            return self._simulate_batch(sequence)
        return self._simulate_string(sequence)

    def _simulate_string(self, sequence: str) -> str:
        rng = make_rng()
        coverage = max(1, self.get_coverage(sequence))
        reads = [
            self._mutate_observed_read(
                sequence, self._simulate_base_read(sequence, rng), rng
            )
            for _ in range(coverage)
        ]
        if coverage == 1:
            return reads[0]
        return _consensus(reads)

    def _simulate_base_read(self, sequence: str, rng: random.Random) -> str:
        return simulate_d2sim(sequence, error_rate=self.error_rate, rng=rng)

    def _mutate_observed_read(
        self, original: str, base_read: str, rng: random.Random
    ) -> str:
        quality = self.quality_profile
        return _mutate_read(base_read, quality, rng, self)

    def _simulate_batch(self, batch: SequenceBatch) -> SequenceBatch:
        return _simulate_batch_impl(self, batch)

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

    def _simulate_base_read(self, sequence: str, rng: random.Random) -> str:
        return simulate_desp(sequence, error_rate=self.error_rate, rng=rng)


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
        coverage: float = 1,
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
        self._current_rates: tuple[float, float, float] | None = None

    def _simulate_cli(self, sequence: str) -> str:
        import logging

        return run_dnarsim_cli(
            sequence,
            self.error_rate,
            self.profile,
            logger=logging.getLogger(__name__).warning,
        )

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

    def _simulate_base_read(self, sequence: str, rng: random.Random) -> str:
        try:
            base = self._simulate_cli(sequence)
            self._current_rates = (
                self.substitution_rate,
                self.insertion_rate,
                self.deletion_rate,
            )
            return base
        except Exception:
            from typing import cast

            base = cast(str, _simulate_fallback_jit(sequence, self.error_rate, rng))
            rates = self._profile_rates
            self._current_rates = (
                rates.get("substitution_rate", self.substitution_rate),
                rates.get("insertion_rate", self.insertion_rate),
                rates.get("deletion_rate", self.deletion_rate),
            )
            return base

    def _mutate_observed_read(
        self, original: str, base_read: str, rng: random.Random
    ) -> str:
        from typing import cast

        sub, ins, dele = self._current_rates or (
            self.substitution_rate,
            self.insertion_rate,
            self.deletion_rate,
        )
        quality = self.quality_profile
        mutated = cast(
            str,
            _mutate_read_jit(
                base_read,
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
        self._current_rates = None
        return mutated


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
    registrar("nanopore", NanoporeChannel())
    registrar("nanopore_d2sim", NanoporeChannel())
    registrar("nanopore_desp", NanoporeDeSPChannel())
    registrar("nanopore_dnarsim", NanoporeDNArSimChannel())
