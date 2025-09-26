"""Wrapper for the optional d2sim nanopore simulator."""
from __future__ import annotations

from typing import Any, Callable, Sequence, Dict, Iterable, Mapping, cast
from copy import deepcopy
from types import ModuleType
import json
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
from ..d2sim_adapter import simulate_d2sim
from ..desp_adapter import simulate_desp
from ..simulator_utils import _run_external, _parse_env_options
from ..api import Simulator
from .base import BaseChannel
from .batch_utils import (
    CONFIG_COVERAGE_KEY,
    CONFIG_DROPOUT_KEY,
    CONFIG_SYNTHESIS_KEY,
    RESULT_CONSENSUS_TOTALS_KEY,
    RESULT_COVERAGE_KEY,
    RESULT_DROPOUT_FLAG_KEY,
    RESULT_MUTATION_LOG_KEY,
    RESULT_MUTATION_TOTALS_KEY,
    RESULT_SYNTHESIS_FLAG_KEY,
    bool_to_str,
    clone_batch,
    finalize_batch_statistics,
    load_coverage_distribution,
    metadata_float,
    mutation_counts,
)
from ..formats import SequenceBatch
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


def _split_context_indels(
    profiles: Mapping[str, Mapping[Any, Any]] | None,
    name: str,
) -> tuple[Dict[str, Dict[int, float]], Dict[str, Dict[int, float]]]:
    """Return separate insertion and deletion context maps.

    ``profiles`` can map contexts either to ``{"insertions": {...}, "deletions": {...}}``
    or to run-length specific mappings such as ``{5: {"insertions": 0.1}}``. When only a
    single probability is provided for a run length, it is applied to both insertions
    and deletions by default. This helper validates the nested indel profiles and
    returns two dictionaries in the normalized format used internally by the
    simulator. Invalid context structures raise ``ValueError``.
    """

    if profiles is None:
        return {}, {}
    if not isinstance(profiles, Mapping):
        raise ValueError(f"{name} must be a mapping of contexts to profiles")

    ctx_ins: Dict[str, Dict[int, float]] = {}
    ctx_del: Dict[str, Dict[int, float]] = {}
    for ctx, ctx_map in profiles.items():
        if not isinstance(ctx_map, Mapping):
            raise ValueError(f"{name}[{ctx}] must be a mapping")
        ctx_key = str(ctx).upper()

        if any(k in {"insertions", "insertion", "deletions", "deletion"} for k in ctx_map):
            # Traditional format with explicit insertion/deletion maps
            extra = set(ctx_map) - {
                "insertions",
                "insertion",
                "deletions",
                "deletion",
            }
            if extra:
                raise ValueError(
                    f"{name}[{ctx}] has invalid keys: {', '.join(map(str, extra))}"
                )
            ins_prof = ctx_map.get("insertions") or ctx_map.get("insertion")
            del_prof = ctx_map.get("deletions") or ctx_map.get("deletion")
            if ins_prof is not None:
                ctx_ins[ctx_key] = _validate_indel_profile(
                    ins_prof, f"{name}[{ctx}].insertions"
                )
            if del_prof is not None:
                ctx_del[ctx_key] = _validate_indel_profile(
                    del_prof, f"{name}[{ctx}].deletions"
                )
            continue

        # Run-length first format: {context: {run_len: {"insertions": x, ...}}}
        for run_len, rates in ctx_map.items():
            try:
                rl = int(run_len)
            except (TypeError, ValueError):
                raise ValueError(f"{name}[{ctx}] run lengths must be integers") from None
            if isinstance(rates, Mapping):
                extra = set(rates) - {
                    "insertions",
                    "insertion",
                    "deletions",
                    "deletion",
                }
                if extra:
                    raise ValueError(
                        f"{name}[{ctx}][{rl}] has invalid keys: {', '.join(map(str, extra))}"
                    )
                ins = rates.get("insertions") or rates.get("insertion")
                dele = rates.get("deletions") or rates.get("deletion")
                if ins is None and dele is None:
                    raise ValueError(
                        f"{name}[{ctx}][{rl}] must specify insertions or deletions"
                    )
                if ins is not None:
                    val = _validate_rate(
                        f"{name}[{ctx}][{rl}].insertions", ins
                    )
                    ctx_ins.setdefault(ctx_key, {})[rl] = val
                if dele is not None:
                    val = _validate_rate(
                        f"{name}[{ctx}][{rl}].deletions", dele
                    )
                    ctx_del.setdefault(ctx_key, {})[rl] = val
            else:
                val = _validate_rate(f"{name}[{ctx}][{rl}]", rates)
                ctx_ins.setdefault(ctx_key, {})[rl] = val
                ctx_del.setdefault(ctx_key, {})[rl] = val
    return ctx_ins, ctx_del

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

_BASE_PROFILE_KEYS = {
    "error_rate",
    "substitution_rate",
    "insertion_rate",
    "deletion_rate",
    "coverage",
    "quality_profile",
}


def _parse_profile(params: Mapping[str, Any]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in params.items():
        if key in {"insertion_profile", "deletion_profile"}:
            prof = value if isinstance(value, Mapping) else None
            parsed[key] = _validate_indel_profile(prof, key)
        elif key in {"context_insertions", "context_deletions"}:
            prof = value if isinstance(value, Mapping) else None
            parsed[key] = _validate_context_profiles(prof, key)
        elif key == "context_indels" and isinstance(value, Mapping):
            ctx_ins, ctx_del = _split_context_indels(value, "context_indels")
            if ctx_ins:
                parsed.setdefault("context_insertions", {}).update(ctx_ins)
            if ctx_del:
                parsed.setdefault("context_deletions", {}).update(ctx_del)
        else:
            parsed[key] = value
    if "error_rate" not in parsed:
        sub = float(parsed.get("substitution_rate", 0.0))
        ins = float(parsed.get("insertion_rate", 0.0))
        dele = float(parsed.get("deletion_rate", 0.0))
        parsed["error_rate"] = sub + ins + dele
    return parsed


def _parse_context_overrides(params: Mapping[str, Any], name: str) -> dict[str, Any]:
    parsed = _parse_profile(params)
    for key in list(parsed):
        if key in _BASE_PROFILE_KEYS:
            parsed.pop(key)
    if not parsed:
        raise ValueError(f"{name} must define context-specific overrides")
    return parsed


def _merge_profiles(
    base: Mapping[str, Any], overrides: Mapping[str, Any]
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key, value in base.items():
        if isinstance(value, Mapping):
            merged[key] = {k: deepcopy(v) for k, v in value.items()}
        else:
            merged[key] = deepcopy(value)
    for key, value in overrides.items():
        if key in {"insertion_profile", "deletion_profile"}:
            existing = {k: float(v) for k, v in merged.get(key, {}).items()}
            for run_len, rate in value.items():
                existing[int(run_len)] = float(rate)
            merged[key] = existing
        elif key in {"context_insertions", "context_deletions"}:
            dest = {
                ctx: {run: float(rate) for run, rate in prof.items()}
                for ctx, prof in merged.get(key, {}).items()
            }
            for ctx, prof in value.items():
                ctx_key = str(ctx).upper()
                dest.setdefault(ctx_key, {})
                for run_len, rate in prof.items():
                    dest[ctx_key][int(run_len)] = float(rate)
            merged[key] = dest
        else:
            merged[key] = deepcopy(value)
    return merged


def _parse_rate_table(tbl: Mapping[str, Any]) -> dict[str, Any]:
    parsed: dict[str, Any] = {
        "substitution_rate": float(tbl.get("substitution_rate", 0.0)),
        "insertion_rate": float(tbl.get("insertion_rate", 0.0)),
        "deletion_rate": float(tbl.get("deletion_rate", 0.0)),
    }
    if "context_errors" in tbl and isinstance(tbl["context_errors"], Mapping):
        parsed["context_errors"] = {
            str(k).upper(): float(v)
            for k, v in tbl["context_errors"].items()
            if isinstance(v, (int, float))
        }
    if "insertion_profile" in tbl:
        parsed["insertion_profile"] = _validate_indel_profile(
            tbl.get("insertion_profile"), "insertion_profile"
        )
    if "deletion_profile" in tbl:
        parsed["deletion_profile"] = _validate_indel_profile(
            tbl.get("deletion_profile"), "deletion_profile"
        )
    if "context_insertions" in tbl:
        parsed["context_insertions"] = _validate_context_profiles(
            tbl.get("context_insertions"), "context_insertions"
        )
    if "context_deletions" in tbl:
        parsed["context_deletions"] = _validate_context_profiles(
            tbl.get("context_deletions"), "context_deletions"
        )
    if "context_indels" in tbl and isinstance(tbl["context_indels"], Mapping):
        ctx_ins, ctx_del = _split_context_indels(
            tbl["context_indels"], "context_indels"
        )
        if ctx_ins:
            parsed.setdefault("context_insertions", {}).update(ctx_ins)
        if ctx_del:
            parsed.setdefault("context_deletions", {}).update(ctx_del)
    return parsed


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
            base_data = yaml_module.safe_load(fh) or {}
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
            context_data = yaml_module.safe_load(fh) or {}
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
            rates_data = yaml_module.safe_load(fh) or {}
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
                data = yaml.safe_load(fh) or {}
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
        rng = make_rng()
        mutated = clone_batch(batch)
        dropout_rate = metadata_float(mutated.metadata, CONFIG_DROPOUT_KEY, 0.0)
        synthesis_loss = metadata_float(mutated.metadata, CONFIG_SYNTHESIS_KEY, 0.0)
        coverage_dist = load_coverage_distribution(
            mutated.metadata.get(CONFIG_COVERAGE_KEY)
        )

        coverage_counts: list[int] = []
        dropout_flags: list[bool] = []
        synthesis_flags: list[bool] = []
        consensus_totals: list[tuple[int, int, int]] = []

        for original, oligo in zip(batch.oligos, mutated.oligos):
            seed = (
                oligo.seed
                if oligo.seed is not None
                else int(rng.random() * (2**32 - 1))
            )
            oligo_rng = random.Random(seed)

            dropped = False
            synth_failed = False
            coverage = 0
            read_logs: list[dict[str, int | str]] = []
            per_read_totals = [0, 0, 0]

            if oligo_rng.random() < synthesis_loss:
                synth_failed = True
            elif oligo_rng.random() < dropout_rate:
                dropped = True

            if not dropped and not synth_failed:
                if coverage_dist:
                    total_weight = sum(coverage_dist.values())
                    threshold = oligo_rng.random() * total_weight if total_weight > 0 else 0.0
                    cumulative = 0.0
                    coverage_choice = 0
                    for cov, weight in sorted(coverage_dist.items()):
                        cumulative += weight
                        coverage_choice = int(cov)
                        if threshold <= cumulative:
                            break
                    coverage = max(0, coverage_choice)
                else:
                    coverage = max(1, int(self.get_coverage(original.sequence)))
                if coverage <= 0:
                    dropped = True

            reads: list[str] = []
            if not dropped and not synth_failed:
                for _ in range(coverage):
                    base_read = self._simulate_base_read(original.sequence, oligo_rng)
                    mutated_read = self._mutate_observed_read(
                        original.sequence, base_read, oligo_rng
                    )
                    reads.append(mutated_read)
                    sub, ins, dele = mutation_counts(original.sequence, mutated_read)
                    per_read_totals[0] += sub
                    per_read_totals[1] += ins
                    per_read_totals[2] += dele
                    read_logs.append(
                        {
                            "read": mutated_read,
                            "substitutions": sub,
                            "insertions": ins,
                            "deletions": dele,
                        }
                    )

            consensus_counts = (0, 0, 0)
            if reads:
                consensus = reads[0] if len(reads) == 1 else _consensus(reads)
                oligo.sequence = consensus
                consensus_counts = mutation_counts(original.sequence, consensus)
            else:
                oligo.sequence = ""
                coverage = 0

            oligo.metadata[RESULT_COVERAGE_KEY] = str(coverage)
            oligo.metadata[RESULT_DROPOUT_FLAG_KEY] = bool_to_str(dropped)
            oligo.metadata[RESULT_SYNTHESIS_FLAG_KEY] = bool_to_str(synth_failed)
            oligo.metadata[RESULT_MUTATION_LOG_KEY] = json.dumps(read_logs)
            oligo.metadata[RESULT_MUTATION_TOTALS_KEY] = json.dumps(
                {
                    "substitutions": per_read_totals[0],
                    "insertions": per_read_totals[1],
                    "deletions": per_read_totals[2],
                }
            )
            oligo.metadata[RESULT_CONSENSUS_TOTALS_KEY] = json.dumps(
                {
                    "substitutions": consensus_counts[0],
                    "insertions": consensus_counts[1],
                    "deletions": consensus_counts[2],
                }
            )

            coverage_counts.append(int(coverage))
            dropout_flags.append(dropped)
            synthesis_flags.append(synth_failed)
            consensus_totals.append(consensus_counts)

        finalize_batch_statistics(
            mutated, coverage_counts, dropout_flags, synthesis_flags, consensus_totals
        )
        return mutated

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
            base = self._simulate_fallback(sequence, self.error_rate, rng)
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

