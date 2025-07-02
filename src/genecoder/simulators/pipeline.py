from __future__ import annotations

from typing import Iterable, List

from ..channels.base import BaseChannel

__all__ = ["ChannelPipeline"]


class ChannelPipeline(BaseChannel):
    """Apply a sequence of channels to a DNA sequence."""

    def __init__(self, channels: Iterable[BaseChannel] | None = None) -> None:
        self.channels: List[BaseChannel] = list(channels or [])

    def add_channel(self, channel: BaseChannel) -> None:
        """Append ``channel`` to the pipeline."""
        self.channels.append(channel)

    def simulate(self, sequence: str) -> str:
        for channel in self.channels:
            sequence = channel.simulate(sequence)
        return sequence
