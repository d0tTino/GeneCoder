from __future__ import annotations

# ruff: noqa: ANN401

"""Base classes for pluggable codecs and FEC backends."""

from ..api import Codec, FEC


class BaseCodec(Codec):
    """Abstract base class for simple codecs."""

    pass


class BaseFEC(FEC):
    """Abstract base class for forward error correction backends."""

    pass

__all__ = ["BaseCodec", "BaseFEC"]

