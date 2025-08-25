from typing import Callable

from genecoder.api import Simulator


class TemplateChannel(Simulator):  # type: ignore[misc]
    """Skeleton channel plugin."""

    def simulate(self, sequence: str) -> str:
        """Return a possibly modified version of ``sequence``."""
        raise NotImplementedError


def register(register_simulator: Callable[[str, Simulator], None]) -> None:
    """Register the channel simulator with GeneCoder."""
    register_simulator("template", TemplateChannel())
