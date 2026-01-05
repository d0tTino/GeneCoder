"""Helpers for validating and merging Nanopore context profiles."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Dict, Mapping, MutableMapping, Tuple

try:  # Optional dependency in minimal environments
    import yaml as _yaml  # type: ignore[import]
except Exception:  # pragma: no cover - exercised when PyYAML is absent
    _yaml = None

__all__ = [
    "BASE_PROFILE_KEYS",
    "load_yaml_data",
    "validate_rate",
    "validate_indel_profile",
    "validate_context_profiles",
    "split_context_indels",
    "parse_profile",
    "parse_context_overrides",
    "merge_profiles",
    "parse_rate_table",
]


BASE_PROFILE_KEYS = {
    "error_rate",
    "substitution_rate",
    "insertion_rate",
    "deletion_rate",
    "coverage",
    "quality_profile",
}


def _coerce_key(value: str) -> str | int:
    try:
        return int(value, 10)
    except (TypeError, ValueError):
        return value


def _coerce_scalar(value: str) -> object:
    lower = value.lower()
    if lower in {"null", "none", "~"}:
        return None
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        if value.startswith("0x"):
            return int(value, 16)
        if value.startswith("0o"):
            return int(value, 8)
        if value.startswith("0b"):
            return int(value, 2)
    except ValueError:
        pass
    try:
        if any(ch in value for ch in ".eE"):
            return float(value)
        return int(value, 10)
    except ValueError:
        return value.strip("'\"")


def _parse_simple_yaml(text: str) -> object:
    """Parse a minimal subset of YAML when PyYAML is unavailable."""

    root: MutableMapping[str | int, object] = {}
    stack: list[Tuple[MutableMapping[str | int, object], int]] = [(root, -1)]

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        key, sep, remainder = raw_line.lstrip().partition(":")
        if not sep:
            continue
        key = _coerce_key(key.strip())
        value = remainder.strip()

        while stack and indent <= stack[-1][1]:
            stack.pop()
        if not stack:
            stack = [(root, -1)]
        current, _ = stack[-1]

        if not value:
            new_map: MutableMapping[str | int, object] = {}
            current[key] = new_map
            stack.append((new_map, indent))
            continue

        current[key] = _coerce_scalar(value)

    return root


def load_yaml_data(text: str, yaml_module: object | None = None) -> object:
    """Return parsed YAML data with graceful fallback when PyYAML is missing."""

    yaml_mod = yaml_module or _yaml
    if yaml_mod is not None:
        try:
            data = yaml_mod.safe_load(text)
        except Exception:
            data = None
        if data not in (None, {}):
            return data

    stripped = text.strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except Exception:
        return _parse_simple_yaml(stripped)


def validate_rate(name: str, rate: float | int) -> float:
    """Return ``rate`` as ``float`` ensuring it lies between 0 and 1."""

    try:
        value = float(rate)
    except (TypeError, ValueError):  # pragma: no cover - validated by callers
        raise ValueError(f"{name} must be a number between 0 and 1") from None
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return value


def validate_indel_profile(
    profile: Mapping[int, float] | None, name: str
) -> Dict[int, float]:
    """Validate an indel profile mapping run-lengths to probabilities."""

    validated: Dict[int, float] = {}
    for run_len, prob in (profile or {}).items():
        try:
            rl = int(run_len)
        except (TypeError, ValueError):
            raise ValueError(f"{name} run lengths must be integers") from None
        validated[rl] = validate_rate(f"{name}[{rl}]", prob)
    return validated


def validate_context_profiles(
    profiles: Mapping[str, Mapping[int, float]] | None, name: str
) -> Dict[str, Dict[int, float]]:
    """Validate mappings of sequence contexts to indel profiles."""

    validated: Dict[str, Dict[int, float]] = {}
    for ctx, prof in (profiles or {}).items():
        if not isinstance(prof, Mapping):
            raise ValueError(
                f"{name}[{ctx}] must be a mapping of run lengths to probabilities"
            )
        validated[str(ctx).upper()] = validate_indel_profile(prof, f"{name}[{ctx}]")
    return validated


def split_context_indels(
    profiles: Mapping[str, Mapping[object, object]] | None,
    name: str,
) -> tuple[Dict[str, Dict[int, float]], Dict[str, Dict[int, float]]]:
    """Normalise combined context indel definitions.

    ``profiles`` can map contexts to a nested structure containing explicit
    ``insertions`` and ``deletions`` keys or to run-length keyed mappings. This
    helper validates both forms and returns separate insertion and deletion
    dictionaries.
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
                ctx_ins[ctx_key] = validate_indel_profile(
                    ins_prof, f"{name}[{ctx}].insertions"
                )
            if del_prof is not None:
                ctx_del[ctx_key] = validate_indel_profile(
                    del_prof, f"{name}[{ctx}].deletions"
                )
            continue

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
                    val = validate_rate(f"{name}[{ctx}][{rl}].insertions", ins)
                    ctx_ins.setdefault(ctx_key, {})[rl] = val
                if dele is not None:
                    val = validate_rate(f"{name}[{ctx}][{rl}].deletions", dele)
                    ctx_del.setdefault(ctx_key, {})[rl] = val
            else:
                val = validate_rate(f"{name}[{ctx}][{rl}]", rates)
                ctx_ins.setdefault(ctx_key, {})[rl] = val
                ctx_del.setdefault(ctx_key, {})[rl] = val
    return ctx_ins, ctx_del


def parse_profile(params: Mapping[str, object]) -> dict[str, object]:
    """Return a validated profile dictionary from ``params``."""

    parsed: dict[str, object] = {}
    for key, value in params.items():
        if key in {"insertion_profile", "deletion_profile"}:
            prof = value if isinstance(value, Mapping) else None
            parsed[key] = validate_indel_profile(prof, key)
        elif key in {"context_insertions", "context_deletions"}:
            prof = value if isinstance(value, Mapping) else None
            parsed[key] = validate_context_profiles(prof, key)
        elif key == "context_indels" and isinstance(value, Mapping):
            ctx_ins, ctx_del = split_context_indels(value, "context_indels")
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


def parse_context_overrides(params: Mapping[str, object], name: str) -> dict[str, object]:
    """Return context overrides without the base-rate fields."""

    parsed = parse_profile(params)
    for key in list(parsed):
        if key in BASE_PROFILE_KEYS:
            parsed.pop(key)
    if not parsed:
        raise ValueError(f"{name} must define context-specific overrides")
    return parsed


def merge_profiles(base: Mapping[str, object], overrides: Mapping[str, object]) -> dict[str, object]:
    """Merge two profile dictionaries, deep-copying nested mappings."""

    merged: dict[str, object] = {}
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


def parse_rate_table(tbl: Mapping[str, object]) -> dict[str, object]:
    """Parse a DNArSim rate table definition."""

    parsed: dict[str, object] = {
        "substitution_rate": float(tbl.get("substitution_rate", 0.0)),
        "insertion_rate": float(tbl.get("insertion_rate", 0.0)),
        "deletion_rate": float(tbl.get("deletion_rate", 0.0)),
    }
    if "coverage" in tbl:
        parsed["coverage"] = float(tbl.get("coverage", 0.0))
    if "context_errors" in tbl and isinstance(tbl["context_errors"], Mapping):
        parsed["context_errors"] = {
            str(k).upper(): float(v)
            for k, v in tbl["context_errors"].items()
            if isinstance(v, (int, float))
        }
    if "insertion_profile" in tbl:
        parsed["insertion_profile"] = validate_indel_profile(
            tbl.get("insertion_profile"), "insertion_profile"
        )
    if "deletion_profile" in tbl:
        parsed["deletion_profile"] = validate_indel_profile(
            tbl.get("deletion_profile"), "deletion_profile"
        )
    if "context_insertions" in tbl:
        parsed["context_insertions"] = validate_context_profiles(
            tbl.get("context_insertions"), "context_insertions"
        )
    if "context_deletions" in tbl:
        parsed["context_deletions"] = validate_context_profiles(
            tbl.get("context_deletions"), "context_deletions"
        )
    if "context_indels" in tbl and isinstance(tbl["context_indels"], Mapping):
        ctx_ins, ctx_del = split_context_indels(tbl["context_indels"], "context_indels")
        if ctx_ins:
            parsed.setdefault("context_insertions", {}).update(ctx_ins)
        if ctx_del:
            parsed.setdefault("context_deletions", {}).update(ctx_del)
    return parsed
