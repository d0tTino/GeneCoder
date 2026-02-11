from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PluginLifecycleState(str, Enum):
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    LOADED = "loaded"
    FAILED = "failed"


@dataclass(slots=True)
class PluginDescriptor:
    name: str
    kind: str
    source: str
    version: str = ""
    license: str = ""
    checksum: str | None = None
    signature: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    state: PluginLifecycleState = PluginLifecycleState.DISCOVERED
    error: str | None = None

    def as_lock_entry(self) -> dict[str, str]:
        return {
            "name": self.name,
            "version": self.version,
            "source": self.source,
            "checksum": self.checksum or "",
            "signature": self.signature or "",
        }
