"""Sequencing simulator implementations and registry."""
from __future__ import annotations

from typing import Dict
import os

from ..plugin_api import Simulator
from ..formats import SequenceBatch
from ..random_utils import reset_rng
from .batch_utils import apply_legacy_simulator
from .pipeline import ChannelPipeline

SIMULATOR_REGISTRY: Dict[str, Simulator] = {}


class BatchSimulatorAdapter(Simulator):
    """Explicit wrapper adding SequenceBatch support to legacy simulators."""

    supports_batches = True

    def __init__(self, delegate: Simulator) -> None:
        self.delegate = delegate

    def simulate(self, sequence: str | SequenceBatch) -> str | SequenceBatch:
        if isinstance(sequence, SequenceBatch):
            return apply_legacy_simulator(sequence, self.delegate.simulate)
        return self.delegate.simulate(sequence)

    def with_profile(self, profile: str) -> Simulator:
        profiled = self.delegate.with_profile(profile)
        if getattr(profiled, "supports_batches", False):
            return profiled
        return BatchSimulatorAdapter(profiled)


def _ensure_batch_simulator(channel: Simulator) -> Simulator:
    if getattr(channel, "supports_batches", False):
        return channel
    if isinstance(channel, BatchSimulatorAdapter):
        return channel
    return BatchSimulatorAdapter(channel)


def register_simulator(name: str, channel: Simulator) -> None:
    """Register ``channel`` under ``name``."""

    SIMULATOR_REGISTRY[name] = _ensure_batch_simulator(channel)


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
    "BatchSimulatorAdapter",
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
        profile_target = channel.delegate if isinstance(channel, BatchSimulatorAdapter) else channel
        if isinstance(profile_target, (IlluminaChannel, IlluminaInSilicoSeqChannel)):
            if prof not in ILLUMINA_PROFILES:
                raise ValueError(f"Unknown Illumina profile: {profile}")
            channel = channel.with_profile(prof)
        elif isinstance(
            profile_target,
            (NanoporeChannel, NanoporeDeSPChannel, NanoporeDNArSimChannel),
        ):
            if prof not in NANOPORE_PROFILES:
                raise ValueError(f"Unknown Nanopore profile: {profile}")
            channel = channel.with_profile(prof)
        else:
            raise ValueError(
                f"Simulator '{simulator}' does not support profiles"
            )

    if os.getenv("GENECODER_SIM_SEED") is not None:
        reset_rng()

    if hasattr(channel, "substitution_prob"):
        old_rate = getattr(channel, "substitution_prob")
        setattr(channel, "substitution_prob", error_rate)
        try:
            return channel.simulate(sequence)
        finally:
            setattr(channel, "substitution_prob", old_rate)
    if hasattr(channel, "error_rate"):
        old_rate = getattr(channel, "error_rate")
        setattr(channel, "error_rate", error_rate)
        try:
            return channel.simulate(sequence)
        finally:
            setattr(channel, "error_rate", old_rate)
    return channel.simulate(sequence)
