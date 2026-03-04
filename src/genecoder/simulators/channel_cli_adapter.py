from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from genecoder.compat.channel_cli import (
    LEGACY_INDEL_PROFILE_NAMES,
    MODERN_INDEL_PROFILES,
    resolve_indel_profile,
)
from genecoder.simulators.nanopore import DNARSIM_RATE_TABLES, NANOPORE_PROFILES


@dataclass(frozen=True)
class ChannelSimulatorSelection:
    simulators: list[tuple[str, dict[str, object]]]
    warnings: list[str]


def _is_rate_set(*values: float | None) -> bool:
    return any(value is not None for value in values)


def adapt_channel_options_to_simulators(
    simulators: Sequence[tuple[str, dict[str, object]]],
    opts: object,
) -> ChannelSimulatorSelection:
    warnings: list[str] = []
    updated: list[tuple[str, dict[str, object]]] = []
    for name, params in simulators:
        new_params = dict(params)
        if name == "illumina" or name.startswith("nanopore"):
            if opts.coverage is not None:
                new_params.setdefault("coverage", opts.coverage)
            if opts.quality_profile is not None:
                new_params.setdefault("quality_profile", opts.quality_profile)
        if name == "illumina":
            if opts.illumina_profile:
                new_params.setdefault("profile", opts.illumina_profile)
            if opts.illumina_depth is not None:
                new_params["coverage"] = opts.illumina_depth
            if opts.illumina_quality is not None:
                new_params["quality_profile"] = opts.illumina_quality
            if opts.illumina_context is not None:
                new_params["context_errors"] = opts.illumina_context
            if opts.illumina_sub_rate is not None:
                new_params["substitution_rate"] = opts.illumina_sub_rate
            if opts.illumina_ins_rate is not None:
                new_params["insertion_rate"] = opts.illumina_ins_rate
            if opts.illumina_del_rate is not None:
                new_params["deletion_rate"] = opts.illumina_del_rate
        if name.startswith("nanopore"):
            selected_profile = opts.nanopore_profile
            profile_source = NANOPORE_PROFILES
            if name == "nanopore_dnarsim":
                selected_profile = opts.dnarsim_profile or opts.nanopore_profile
                profile_source = DNARSIM_RATE_TABLES
            if selected_profile:
                prof = profile_source.get(selected_profile)
                if prof is None:
                    label = "DNArSim" if name == "nanopore_dnarsim" else "Nanopore"
                    raise ValueError(f"Unknown {label} profile: {selected_profile}")
                for key, value in prof.items():
                    new_params.setdefault(key, value)
                if name == "nanopore_dnarsim":
                    new_params.setdefault("profile", selected_profile)
            if opts.nanopore_depth is not None:
                new_params["coverage"] = opts.nanopore_depth
            if opts.nanopore_quality is not None:
                new_params["quality_profile"] = opts.nanopore_quality
            if opts.nanopore_context is not None:
                new_params["context_errors"] = opts.nanopore_context
            if opts.nanopore_sub_rate is not None:
                new_params["substitution_rate"] = opts.nanopore_sub_rate
            if opts.nanopore_ins_rate is not None:
                new_params["insertion_rate"] = opts.nanopore_ins_rate
            if opts.nanopore_del_rate is not None:
                new_params["deletion_rate"] = opts.nanopore_del_rate
            if name == "nanopore_dnarsim":
                for unsupported in ("insertion_profile", "deletion_profile"):
                    new_params.pop(unsupported, None)
        if name == "indel":
            profile_name, compat_warnings = resolve_indel_profile(
                requested_profile=opts.indel_profile,
                has_explicit_rates=_is_rate_set(opts.sub_rate, opts.ins_rate, opts.del_rate),
            )
            warnings.extend(compat_warnings)
            if profile_name is not None:
                new_params.setdefault("profile", profile_name)
            if opts.sub_rate is not None:
                new_params["substitution_prob"] = opts.sub_rate
            if opts.ins_rate is not None:
                new_params["insertion_prob"] = opts.ins_rate
            if opts.del_rate is not None:
                new_params["deletion_prob"] = opts.del_rate
        if name == "simple" and opts.sub_rate is not None:
            new_params["substitution_prob"] = opts.sub_rate
        if name == "illumina_builtin":
            if opts.sub_rate is not None:
                new_params["error_rate"] = opts.sub_rate
            if opts.illumina_depth is not None:
                new_params["coverage_depth"] = opts.illumina_depth
            if opts.illumina_quality is not None:
                new_params["quality_distribution"] = opts.illumina_quality
        updated.append((name, new_params))
    return ChannelSimulatorSelection(simulators=updated, warnings=warnings)


def apply_run_indel_profile_compat(
    simulators: Sequence[tuple[str, dict[str, object]]],
    *,
    indel_profile: str | None,
) -> tuple[list[tuple[str, dict[str, object]]], list[str]]:
    profile_name, warnings = resolve_indel_profile(
        requested_profile=indel_profile,
        has_explicit_rates=False,
    )
    resolved: list[tuple[str, dict[str, object]]] = []
    for name, params in simulators:
        updated = dict(params)
        if name == "indel" and profile_name is not None and "profile" not in updated:
            if not any(
                key in updated
                for key in ("substitution_prob", "insertion_prob", "deletion_prob", "error_rate")
            ):
                updated["profile"] = profile_name
        resolved.append((name, updated))
    return resolved, warnings


def validate_indel_profile(profile: str) -> None:
    lowered = profile.lower()
    if lowered in MODERN_INDEL_PROFILES or lowered in LEGACY_INDEL_PROFILE_NAMES:
        return
    raise ValueError(f"Unknown indel profile: {profile}")
