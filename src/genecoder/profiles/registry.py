from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping
import warnings


LegacyProfilePolicy = Literal["strict", "compat"]


PROFILE_ALIAS_TABLE: dict[str, tuple[str, str]] = {
    "miseq": ("illumina", "miseq"),
    "hiseq": ("illumina", "hiseq"),
    "novaseq": ("illumina", "novaseq"),
    "nova": ("illumina", "novaseq"),
    "minion": ("nanopore", "minion"),
    "promethion": ("nanopore", "promethion"),
    "r9": ("nanopore_dnarsim", "r9"),
    "r10.3": ("nanopore_dnarsim", "r10.3"),
    "r10.4": ("nanopore_dnarsim", "r10.4"),
}


@dataclass(frozen=True)
class VersionedProfile:
    schema_version: int
    kind: str
    name: str
    parameters: Mapping[str, Any]


@dataclass(frozen=True)
class ResolvedChannelProfiles:
    illumina_profile: str | None = None
    nanopore_profile: str | None = None
    dnarsim_profile: str | None = None


def resolve_channel_profile_alias(alias: str) -> tuple[str, str]:
    lowered = alias.lower()
    if lowered not in PROFILE_ALIAS_TABLE:
        raise ValueError(f"Unknown profile alias: {alias}")
    return PROFILE_ALIAS_TABLE[lowered]


def canonicalize_profile_name(name: str | None) -> str | None:
    if not name:
        return None
    lowered = name.lower()
    if lowered in PROFILE_ALIAS_TABLE:
        return PROFILE_ALIAS_TABLE[lowered][1]
    return name


def resolve_named_profiles(
    *,
    profile: str | None = None,
    illumina_profile: str | None = None,
    nanopore_profile: str | None = None,
    dnarsim_profile: str | None = None,
) -> ResolvedChannelProfiles:
    resolved_illumina = canonicalize_profile_name(illumina_profile)
    resolved_nanopore = canonicalize_profile_name(nanopore_profile)
    resolved_dnarsim = canonicalize_profile_name(dnarsim_profile)

    if profile:
        family, preset = resolve_channel_profile_alias(profile)
        if family == "illumina":
            resolved_illumina = preset
        elif family == "nanopore_dnarsim":
            resolved_dnarsim = preset
        else:
            resolved_nanopore = preset
    return ResolvedChannelProfiles(
        illumina_profile=resolved_illumina,
        nanopore_profile=resolved_nanopore,
        dnarsim_profile=resolved_dnarsim,
    )


def policy_from_legacy_flag(*, allow_legacy_dict: bool) -> LegacyProfilePolicy:
    return "compat" if allow_legacy_dict else "strict"


def validate_profile_schema(profile: Mapping[str, Any], *, kind: str) -> VersionedProfile:
    schema_version = int(profile.get("schema_version", 1))
    if schema_version != 1:
        raise ValueError(f"Unsupported {kind} profile schema_version: {schema_version}")
    params = profile.get("parameters")
    if not isinstance(params, Mapping):
        raise ValueError(f"{kind} profile requires 'parameters' mapping")
    name = str(profile.get("name") or kind)
    return VersionedProfile(schema_version=schema_version, kind=kind, name=name, parameters=dict(params))


def resolve_versioned_profile(
    value: str | Mapping[str, Any] | None,
    *,
    kind: str,
    presets: Mapping[str, VersionedProfile],
    policy: LegacyProfilePolicy = "strict",
) -> VersionedProfile | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        if "parameters" not in value:
            if policy == "strict":
                raise ValueError(
                    f"{kind} profile mappings must be versioned with schema_version/name/parameters"
                )
            warnings.warn(
                f"Raw dict-based {kind} profiles are deprecated; use a versioned profile object.",
                DeprecationWarning,
                stacklevel=2,
            )
            value = {
                "schema_version": 1,
                "kind": kind,
                "name": "custom",
                "parameters": dict(value),
            }
        return validate_profile_schema(value, kind=kind)

    path = Path(value)
    if path.is_file():
        from genecoder.config.loader import load_mapping_file

        loaded = dict(load_mapping_file(path))
        if "parameters" not in loaded:
            if policy == "strict":
                raise ValueError(
                    f"{kind} profile mappings must be versioned with schema_version/name/parameters"
                )
            warnings.warn(
                f"Raw dict-based {kind} profiles are deprecated; use a versioned profile object.",
                DeprecationWarning,
                stacklevel=2,
            )
            loaded = {
                "schema_version": 1,
                "kind": kind,
                "name": path.stem,
                "parameters": loaded,
            }
        return validate_profile_schema(loaded, kind=kind)
    return presets.get(str(value).lower())


def available_profiles() -> Mapping[str, tuple[str, str]]:
    return PROFILE_ALIAS_TABLE


def available_profile_help() -> dict[str, str]:
    from genecoder.simulators.illumina import ILLUMINA_PROFILES
    from genecoder.simulators.nanopore import DNARSIM_RATE_TABLES, NANOPORE_PROFILES

    return {
        "illumina": ", ".join(sorted(ILLUMINA_PROFILES)),
        "nanopore": ", ".join(sorted(NANOPORE_PROFILES)),
        "dnarsim": ", ".join(sorted(DNARSIM_RATE_TABLES)),
        "aliases": ", ".join(sorted(PROFILE_ALIAS_TABLE)),
    }
