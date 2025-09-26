from __future__ import annotations

from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..formats import SequenceBatch

__all__ = ["BaseChannel"]


@runtime_checkable
class BaseChannel(Protocol):
    """Protocol for DNA read simulators."""

    def simulate(self, sequence: str | "SequenceBatch") -> str | "SequenceBatch":
        """Return a possibly corrupted version of ``sequence``."""
        ...
