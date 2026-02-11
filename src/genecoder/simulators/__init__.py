"""Sequencing simulator implementations and registry."""
from __future__ import annotations

from typing import Dict, Type
import os

from ..plugin_api import Simulator
from ..formats import SequenceBatch
from ..random_utils import reset_rng
from .batch_utils import apply_legacy_simulator
from .pipeline import ChannelPipeline

SIMULATOR_REGISTRY: Dict[str, Simulator] = {}

_ADAPTER_CACHE: Dict[Type[Simulator], Type[Simulator]] = {}


def _get_batch_adapter(base_cls: Type[Simulator]) -> Type[Simulator]:
    if getattr(base_cls, "supports_batches", False):
        return base_cls
    adapter = _ADAPTER_CACHE.get(base_cls)
    if adapter is not None:
        return adapter

    class BatchAdapter(base_cls):  # type: ignore[misc]
        """Auto-generated adapter adding SequenceBatch support."""

        supports_batches = True

        def simulate(self, sequence: str | SequenceBatch) -> str | SequenceBatch:  # type: ignore[override]
            if isinstance(sequence, SequenceBatch):
                return apply_legacy_simulator(
                    sequence,
                    super(BatchAdapter, self).simulate,  # type: ignore[misc]
                )
            return super(BatchAdapter, self).simulate(sequence)  # type: ignore[misc]

        def with_profile(self, profile: str):  # type: ignore[override]
            result = super(BatchAdapter, self).with_profile(profile)
            if isinstance(result, base_cls) and not getattr(
                result.__class__, "supports_batches", False
            ):
                result.__class__ = _get_batch_adapter(result.__class__)
            return result

    BatchAdapter.__name__ = f"{base_cls.__name__}BatchAdapter"
    BatchAdapter.__qualname__ = BatchAdapter.__name__
    BatchAdapter.__module__ = base_cls.__module__
    _ADAPTER_CACHE[base_cls] = BatchAdapter
    return BatchAdapter


def register_simulator(name: str, channel: Simulator) -> None:
    """Register ``channel`` under ``name``."""

    adapter_cls = _get_batch_adapter(channel.__class__)
    if adapter_cls is not channel.__class__:
        channel.__class__ = adapter_cls  # type: ignore[misc]
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
