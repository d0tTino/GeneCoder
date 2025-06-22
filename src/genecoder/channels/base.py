from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["BaseChannel"]


@runtime_checkable
class BaseChannel(Protocol):
    """Protocol for DNA read simulators."""

    def simulate(self, sequence: str) -> str:
        """Return a possibly corrupted version of ``sequence``."""
        ...
