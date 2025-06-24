from typing import Callable

from genecoder.channels.base import BaseChannel


class PassthroughChannel:
    """Simple channel that returns sequences unchanged."""

    def simulate(self, sequence: str) -> str:
        return sequence


def register(register_simulator: Callable[[str, BaseChannel], None]) -> None:
    """Register the example simulator."""

    register_simulator("example", PassthroughChannel())
