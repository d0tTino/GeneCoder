"""Sequencing simulator implementations and registry."""
from __future__ import annotations

from typing import Dict

from ..api import Simulator
from .pipeline import ChannelPipeline

SIMULATOR_REGISTRY: Dict[str, Simulator] = {}


def register_simulator(name: str, channel: Simulator) -> None:
    """Register ``channel`` under ``name``."""
    SIMULATOR_REGISTRY[name] = channel

from .base import BaseChannel, BaseSimulator
from .illumina import (
    IlluminaChannel,
    IlluminaInSilicoSeqChannel,
    ILLUMINA_PROFILES,
)
from .nanopore import (
    NanoporeChannel,
    NanoporeDeSPChannel,
    NanoporeDNArSimChannel,
    NANOPORE_PROFILES,
)

__all__ = [
    "SIMULATOR_REGISTRY",
    "register_simulator",
    "BaseChannel",
    "BaseSimulator",
    "IlluminaChannel",
    "IlluminaInSilicoSeqChannel",
    "NanoporeChannel",
    "NanoporeDeSPChannel",
    "ChannelPipeline",
    "simulate_reads",
]


def simulate_reads(
    sequence: str,
    simulator: str,
    error_rate: float = 0.05,
    profile: str | None = None,
) -> str:
    """Return ``sequence`` processed by the named simulator.

    ``profile`` selects a preset for supported simulators.
    """

    try:
        channel = SIMULATOR_REGISTRY[simulator]
    except KeyError as exc:
        raise ValueError(f"Unknown simulator: {simulator}") from exc

    if profile is not None:
        prof = profile.lower()
        if isinstance(channel, (IlluminaChannel, IlluminaInSilicoSeqChannel)):
            if prof not in ILLUMINA_PROFILES:
                raise ValueError(f"Unknown Illumina profile: {profile}")
            channel = channel.with_profile(prof)
        elif isinstance(
            channel,
            (NanoporeChannel, NanoporeDeSPChannel, NanoporeDNArSimChannel),
        ):
            if prof not in NANOPORE_PROFILES:
                raise ValueError(f"Unknown Nanopore profile: {profile}")
            channel = channel.with_profile(prof)
        else:
            raise ValueError(
                f"Simulator '{simulator}' does not support profiles"
            )

    if hasattr(channel, "error_rate"):
        old_rate = getattr(channel, "error_rate")
        setattr(channel, "error_rate", error_rate)
        try:
            return channel.simulate(sequence)
        finally:
            setattr(channel, "error_rate", old_rate)
    return channel.simulate(sequence)
