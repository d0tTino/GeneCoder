from typing import Callable

from genecoder.api import Visualizer


class ExampleVisualizer(Visualizer):  # type: ignore[misc]
    """Trivial visualizer returning the input sequence unchanged."""

    def visualize(self, sequence: str, /, **kwargs: object) -> str:
        return sequence


def register(register_visualizer: Callable[[str, type[Visualizer]], None]) -> None:
    """Register the example visualizer."""

    register_visualizer("example", ExampleVisualizer)
