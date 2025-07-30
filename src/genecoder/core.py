from __future__ import annotations

"""Simple encode/ECC/channel/decode pipeline utilities."""

from pathlib import Path
from typing import Any, Mapping, Tuple, Dict

from .gc_constrained_encoder import calculate_gc_content
from .utils import get_max_homopolymer_length

from .plugin_manager import CODEC_REGISTRY, FEC_REGISTRY, init_plugins
from .simulators import SIMULATOR_REGISTRY

__all__ = ["run_pipeline"]


def run_pipeline(
    codec: str,
    fec: str | None,
    channel: str | None,
    input_path: str,
    output_path: str,
) -> Tuple[bytes, Dict[str, float | int]]:
    """Process ``input_path`` through the selected codec, FEC and channel.

    The decoded bytes are written to ``output_path`` and also returned.
    """
    init_plugins()

    if codec not in CODEC_REGISTRY:
        raise ValueError(f"Unknown codec: {codec}")
    if fec and fec not in FEC_REGISTRY:
        raise ValueError(f"Unknown FEC: {fec}")
    if channel and channel != "none" and channel not in SIMULATOR_REGISTRY:
        raise ValueError(f"Unknown channel: {channel}")

    data = Path(input_path).read_bytes()

    fec_info: Mapping[str, Any] | None = None
    if fec:
        data, fec_info = FEC_REGISTRY[fec]["encode"](data)

    dna = CODEC_REGISTRY[codec]["encode"](data)

    if channel and channel != "none":
        dna = SIMULATOR_REGISTRY[channel].simulate(dna)

    gc_content = calculate_gc_content(dna)
    max_homopolymer = get_max_homopolymer_length(dna)

    decoded_any = CODEC_REGISTRY[codec]["decode"](dna)
    assert isinstance(decoded_any, (bytes, bytearray))
    decoded = bytes(decoded_any)

    if fec:
        assert fec_info is not None
        decoded, _ = FEC_REGISTRY[fec]["decode"](decoded, fec_info)

    Path(output_path).write_bytes(decoded)
    return decoded, {"gc_content": gc_content, "max_homopolymer": max_homopolymer}
