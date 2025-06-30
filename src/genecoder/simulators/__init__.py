"""Sequencing simulator implementations."""
from __future__ import annotations

from ..plugins import SIMULATOR_REGISTRY

from .base import BaseSimulator
from .illumina import IlluminaChannel
from .adv_nanopore import AdvancedNanoporeChannel
from .replication import ReplicationSimulator
from .transcription import TranscriptionSimulator

__all__ = [
    "BaseSimulator",
    "IlluminaChannel",
    "AdvancedNanoporeChannel",
    "ReplicationSimulator",
    "TranscriptionSimulator",
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
