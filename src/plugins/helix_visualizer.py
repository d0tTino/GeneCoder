from typing import Callable

from genecoder.api import Visualizer
from genecoder.app_helpers import EncodeResult, DecodeResult
from genecoder.helix_view import show_helix_ui


class HelixVisualizer(Visualizer):  # type: ignore[misc]
    """Simple visualizer showing a helix view for encoded DNA."""

    def visualize(
        self, result: EncodeResult | DecodeResult, /, **kwargs: object
    ) -> None:
        if isinstance(result, EncodeResult):
            show_helix_ui(result.encoded_dna, **kwargs)
        else:
            raise TypeError("HelixVisualizer supports EncodeResult only")


def register(register_visualizer: Callable[[str, type[Visualizer]], None]) -> None:
    """Register the helix visualizer."""

    register_visualizer("helix", HelixVisualizer)
