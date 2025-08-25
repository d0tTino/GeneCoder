from __future__ import annotations

from dataclasses import dataclass
import argparse
import os


@dataclass
class EncodeOptions:
    """Options for the GUI/async encoding helpers."""

    method: str
    add_parity: bool = False
    k_value: int = 7
    fec_method: str = "None"  # "None", "Triple-Repeat", "Hamming(7,4)", "Reed-Solomon"
    gc_min: float = 0.45
    gc_max: float = 0.55
    max_homopolymer: int = 3
    window_size: int = 50
    step_size: int = 10
    min_homopolymer_len: int = 4
    alphabet: str = "base4"


@dataclass
class EncodingOptions:
    """Options for the CLI encoding pipeline."""

    method: str
    add_parity: bool
    k_value: int
    parity_rule: str
    fec: str | None
    gc_min: float
    gc_max: float
    max_homopolymer: int
    alphabet: str = "base4"
    seed: int | None = None
    rs_symbol_size: int | None = None
    rs_primitive: int | None = None


@dataclass
class DecodingOptions:
    """Options for the CLI decoding pipeline."""

    method: str
    check_parity: bool
    k_value: int
    parity_rule: str
    alphabet: str
    seed: int | None = None


# Offline mode ------------------------------------------------------------

OFFLINE: bool = bool(os.getenv("GENECODER_OFFLINE"))


def add_offline_flag(parser: argparse.ArgumentParser) -> None:
    """Register the ``--offline`` flag on a CLI parser."""

    parser.add_argument(
        "--offline",
        action="store_true",
        help="Disable network features and cloud modules",
    )


def set_offline(offline: bool) -> None:
    """Enable or disable offline mode globally."""

    global OFFLINE
    OFFLINE = offline
    if offline:
        os.environ["GENECODER_OFFLINE"] = "1"
    else:
        os.environ.pop("GENECODER_OFFLINE", None)
