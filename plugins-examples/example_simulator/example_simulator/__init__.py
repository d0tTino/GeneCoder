from typing import Callable

from genecoder.api import Simulator


class PassthroughChannel(Simulator):  # type: ignore[misc]
    """Simple channel that returns sequences unchanged."""

    def simulate(self, sequence: str) -> str:
        return sequence


def register(register_simulator: Callable[[str, Simulator], None]) -> None:
    """Register the example simulator."""

    register_simulator("example", PassthroughChannel())
