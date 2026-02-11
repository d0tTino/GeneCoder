"""Illumina sequencing simulators."""
from __future__ import annotations

from typing import Callable

from .. import register_simulator as _register_simulator
from ...plugin_api import Simulator
from .channel import IlluminaChannel, IlluminaProfile, ILLUMINA_PROFILES
from .cli import IlluminaD2SimChannel, IlluminaInSilicoSeqChannel, simulate_insilicoseq

__all__ = [
    "IlluminaChannel",
    "IlluminaProfile",
    "IlluminaD2SimChannel",
    "IlluminaInSilicoSeqChannel",
    "simulate_insilicoseq",
    "register",
    "ILLUMINA_PROFILES",
]


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    channel = IlluminaChannel()
    registrar("illumina", channel)
    registrar("illumina_builtin", channel)
    registrar("illumina_d2sim", IlluminaD2SimChannel())
    registrar("illumina_insilicoseq", IlluminaInSilicoSeqChannel())
