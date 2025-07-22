from __future__ import annotations

# ruff: noqa: ANN401

"""Base classes for pluggable codecs and FEC backends."""

from abc import ABC, abstractmethod
from typing import Any, Mapping, Tuple


class BaseCodec(ABC):
    """Abstract base class for simple codecs."""

    @abstractmethod
    def encode(self, data: bytes, /, **kwargs: Any) -> Any:
        """Encode ``data`` and return the encoded representation."""

    @abstractmethod
    def decode(self, encoded: Any, /, **kwargs: Any) -> bytes:
        """Decode ``encoded`` data back into bytes."""


class BaseFEC(ABC):
    """Abstract base class for forward error correction backends."""

    @abstractmethod
    def encode(self, data: bytes, /, **kwargs: Any) -> Tuple[bytes, Mapping[str, Any]]:
        """Encode ``data`` returning encoded bytes and associated info."""

    @abstractmethod
    def decode(self, encoded: bytes, info: Mapping[str, Any], /, **kwargs: Any) -> Tuple[bytes, int]:
        """Decode ``encoded`` bytes using ``info`` returning the original data and number of corrections."""

__all__ = ["BaseCodec", "BaseFEC"]

