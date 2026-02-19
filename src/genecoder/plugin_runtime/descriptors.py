from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class PluginLifecycleState(str, Enum):
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    DISABLED = "disabled"
    LOADED = "loaded"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


PLUGIN_DESCRIPTOR_VERSION = "1.0"
PluginKind = Literal["codec", "fec", "simulator", "visualizer", "package", "metadata"]


@dataclass(slots=True, frozen=True)
class RegistrationCapabilities:
    deterministic: bool = True
    supports_streaming: bool = False


@dataclass(slots=True, frozen=True)
class ValidationContract:
    encode_input: str = "bytes"
    encode_output: str = "bytes"
    decode_input: str = "bytes"
    decode_output: str = "bytes"


@dataclass(slots=True)
class RuntimePluginDescriptor:
    api_version: str
    name: str
    kind: PluginKind
    implementation: object
    capabilities: RegistrationCapabilities = field(default_factory=RegistrationCapabilities)
    validation: ValidationContract = field(default_factory=ValidationContract)
    metadata: dict[str, Any] = field(default_factory=dict)


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
