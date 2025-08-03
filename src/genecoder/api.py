from __future__ import annotations
# ruff: noqa: ANN401

"""Public abstract interfaces for GeneCoder plugins."""

from abc import ABC, abstractmethod
from typing import Any, Mapping, Tuple


__all__ = ["Codec", "FEC", "Simulator", "Visualizer"]


class Codec(ABC):
    """Abstract base class for simple codecs."""

    @abstractmethod
    def encode(self, data: bytes, /, **kwargs: Any) -> Any:
        """Encode ``data`` and return the encoded representation."""

    @abstractmethod
    def decode(self, encoded: Any, /, **kwargs: Any) -> bytes:
        """Decode ``encoded`` data back into bytes."""


class FEC(ABC):
    """Abstract base class for forward error correction backends."""

    @abstractmethod
    def encode(self, data: bytes, /, **kwargs: Any) -> Tuple[bytes, Mapping[str, Any]]:
        """Encode ``data`` returning encoded bytes and associated info."""

    @abstractmethod
    def decode(self, encoded: bytes, info: Mapping[str, Any], /, **kwargs: Any) -> Tuple[bytes, int]:
        """Decode ``encoded`` bytes using ``info`` returning the original data and number of corrections."""


class Simulator(ABC):
    """Abstract base class for read simulators."""

    @abstractmethod
    def simulate(self, sequence: str) -> str:
        """Return a possibly corrupted version of ``sequence``."""

    def with_profile(self, profile: str) -> "Simulator":
        """Return a copy of the simulator configured for ``profile``.

        Implementations should override this method if they support
        applying external error profiles. The default implementation
        raises :class:`NotImplementedError`.
        """

        raise NotImplementedError


class Visualizer(ABC):
    """Abstract base class for sequence visualizers."""

    @abstractmethod
    def visualize(self, sequence: str, /, **kwargs: Any) -> Any:
        """Return a visualization of ``sequence``."""

