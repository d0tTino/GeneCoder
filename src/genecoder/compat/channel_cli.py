from __future__ import annotations

from typing import Final

MODERN_INDEL_PROFILES: Final[dict[str, dict[str, float]]] = {
    "illumina": {
        "substitution_prob": 0.002,
        "insertion_prob": 0.0001,
        "deletion_prob": 0.0001,
    },
    "nanopore": {
        "substitution_prob": 0.01,
        "insertion_prob": 0.02,
        "deletion_prob": 0.02,
    },
}

LEGACY_INDEL_PROFILE_ALIASES: Final[dict[str, str]] = {
    "illumina_adapter": "illumina",
    "nanopore_adapter": "nanopore",
}

LEGACY_INDEL_PROFILE_NAMES: Final[set[str]] = set(LEGACY_INDEL_PROFILE_ALIASES)
LEGACY_DEFAULT_INDEL_PROFILE: Final[str] = "illumina_adapter"


def resolve_indel_profile(
    *,
    requested_profile: str | None,
    has_explicit_rates: bool,
) -> tuple[str | None, list[str]]:
    warnings: list[str] = []
    profile = requested_profile
    if profile is None and not has_explicit_rates:
        profile = LEGACY_DEFAULT_INDEL_PROFILE
        warnings.append(
            "Using legacy implicit indel default profile; migrate to --simulator indel --indel-profile illumina."
        )
    if profile is None:
        return None, warnings

    lowered = profile.lower()
    if lowered in LEGACY_INDEL_PROFILE_ALIASES:
        warnings.append(
            f"Legacy indel profile '{profile}' is deprecated; using '{LEGACY_INDEL_PROFILE_ALIASES[lowered]}' instead."
        )
        return LEGACY_INDEL_PROFILE_ALIASES[lowered], warnings
    if lowered in MODERN_INDEL_PROFILES:
        if requested_profile is not None:
            warnings.append(
                "--indel-profile is a compatibility flag and may be removed; prefer simulator config in workflow YAML."
            )
        return lowered, warnings
    raise ValueError(f"Unknown indel profile: {profile}")

