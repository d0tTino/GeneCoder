"""Sequencing simulator implementations and registry."""
from __future__ import annotations

from typing import Dict

from ..channels.base import BaseChannel
from .pipeline import ChannelPipeline

SIMULATOR_REGISTRY: Dict[str, BaseChannel] = {}


def register_simulator(name: str, channel: BaseChannel) -> None:
    """Register ``channel`` under ``name``."""
    SIMULATOR_REGISTRY[name] = channel

from .base import BaseSimulator
from .illumina import IlluminaChannel
from .illumina_profile import IlluminaProfileChannel
from .adv_nanopore import AdvancedNanoporeChannel
from .replication import ReplicationSimulator
from .transcription import TranscriptionSimulator
from .translation import TranslationSimulator

__all__ = [
    "SIMULATOR_REGISTRY",
    "register_simulator",
    "BaseSimulator",
    "IlluminaChannel",
    "IlluminaProfileChannel",
    "AdvancedNanoporeChannel",
    "ReplicationSimulator",
    "TranscriptionSimulator",
    "TranslationSimulator",
    "ChannelPipeline",
    "simulate_reads",
]


def simulate_reads(sequence: str, simulator: str, error_rate: float = 0.05) -> str:
    """Return ``sequence`` processed by the named simulator."""

    try:
        channel = SIMULATOR_REGISTRY[simulator]
    except KeyError as exc:
        raise ValueError(f"Unknown simulator: {simulator}") from exc

    if hasattr(channel, "error_rate"):
        old_rate = getattr(channel, "error_rate")
        setattr(channel, "error_rate", error_rate)
        try:
            return channel.simulate(sequence)
        finally:
            setattr(channel, "error_rate", old_rate)
    return channel.simulate(sequence)
