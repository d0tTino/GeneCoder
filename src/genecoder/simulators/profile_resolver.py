from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

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


def available_profiles() -> Mapping[str, tuple[str, str]]:
    return PROFILE_ALIAS_TABLE


def available_profile_help() -> dict[str, str]:
    from .illumina import ILLUMINA_PROFILES
    from .nanopore import DNARSIM_RATE_TABLES, NANOPORE_PROFILES

    return {
        "illumina": ", ".join(sorted(ILLUMINA_PROFILES)),
        "nanopore": ", ".join(sorted(NANOPORE_PROFILES)),
        "dnarsim": ", ".join(sorted(DNARSIM_RATE_TABLES)),
        "aliases": ", ".join(sorted(PROFILE_ALIAS_TABLE)),
    }
