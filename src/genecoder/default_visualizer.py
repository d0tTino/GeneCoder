from __future__ import annotations

"""Default Visualizer implementation for GeneCoder."""

from typing import Mapping, Callable
import base64

from .plugin_api import Visualizer
from .plugin_manager import register_visualizer as _register_visualizer
from .plotting import (
    calculate_windowed_gc_content,
    identify_homopolymer_regions,
    generate_sequence_analysis_plot,
)


class DefaultVisualizer(Visualizer):
    """Generate GC distribution and homopolymer plots."""

    def visualize(
        self,
        sequence: str,
        /,
        *,
        window_size: int = 50,
        step_size: int = 10,
        min_homopolymer_len: int = 4,
        **_: object,
    ) -> Mapping[str, str]:
        """Return base64-encoded PNG plots for ``sequence``."""

        gc_data = calculate_windowed_gc_content(sequence, window_size, step_size)
        homopolymers = identify_homopolymer_regions(sequence, min_homopolymer_len)
        buf = generate_sequence_analysis_plot(gc_data, homopolymers, len(sequence))
        plot_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        buf.close()
        return {"sequence_analysis": plot_b64}


def register(
    registrar: Callable[[str, Visualizer | type[Visualizer]], None] = _register_visualizer,
) -> None:
    """Register the default visualizer."""

    registrar("default", DefaultVisualizer)
