"""Canonical simple simulator plugin entry point."""
from __future__ import annotations

from typing import Callable

from genecoder.plugin_api import Simulator
from genecoder.channel_engine.legacy_adapter import Channel as _LegacyChannel
from genecoder.simulators import register_simulator as _register_simulator


def register(registrar: Callable[[str, Simulator], None] = _register_simulator) -> None:
    """Register the built-in ``simple`` simulator."""

    registrar("simple", _LegacyChannel(substitution_prob=0.05))
