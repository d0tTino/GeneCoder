from __future__ import annotations

from typing import Any, Callable

ENTRY_POINT_GROUPS: dict[str, str] = {
    "genecoder.plugins": "codec",
    "genecoder.fec": "FEC",
    "genecoder.simulators": "simulator",
    "genecoder.visualizers": "visualizer",
}


def entry_point_registrars(
    *,
    register_codec: Callable[..., Any],
    register_fec: Callable[..., Any],
    register_simulator: Callable[..., Any],
    register_visualizer: Callable[..., Any],
) -> dict[str, tuple[Callable[..., Any], str]]:
    return {
        "genecoder.plugins": (register_codec, ENTRY_POINT_GROUPS["genecoder.plugins"]),
        "genecoder.fec": (register_fec, ENTRY_POINT_GROUPS["genecoder.fec"]),
        "genecoder.simulators": (register_simulator, ENTRY_POINT_GROUPS["genecoder.simulators"]),
        "genecoder.visualizers": (register_visualizer, ENTRY_POINT_GROUPS["genecoder.visualizers"]),
    }
