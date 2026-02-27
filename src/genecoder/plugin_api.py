from __future__ import annotations
# ruff: noqa: ANN401

"""Public abstract interfaces and capability contracts for GeneCoder plugins."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol, Tuple

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .formats import SequenceBatch


PLUGIN_INTERFACE_SEMVER = "1.0.0"

__all__ = [
    "PLUGIN_INTERFACE_SEMVER",
    "Codec",
    "FEC",
    "Simulator",
    "Visualizer",
    "CodecCapability",
    "FECCapability",
    "SimulatorCapability",
    "VisualizerCapability",
]


class CapabilityContract(Protocol):
    """Typed capability contract implemented by runtime plugin descriptors."""

    interface: str
    interface_version: str
    deterministic: bool


@dataclass(slots=True, frozen=True)
class CodecCapability:
    interface: Literal["codec"] = "codec"
    interface_version: str = PLUGIN_INTERFACE_SEMVER
    deterministic: bool = True
    supports_streaming: bool = False


@dataclass(slots=True, frozen=True)
class FECCapability:
    interface: Literal["fec"] = "fec"
    interface_version: str = PLUGIN_INTERFACE_SEMVER
    deterministic: bool = True
    supports_streaming: bool = False


@dataclass(slots=True, frozen=True)
class SimulatorCapability:
    interface: Literal["simulator"] = "simulator"
    interface_version: str = PLUGIN_INTERFACE_SEMVER
    deterministic: bool = False
    supports_profiles: bool = False


@dataclass(slots=True, frozen=True)
class VisualizerCapability:
    interface: Literal["visualizer"] = "visualizer"
    interface_version: str = PLUGIN_INTERFACE_SEMVER
    deterministic: bool = True
    supports_interactive: bool = False


class Codec(ABC):
    @abstractmethod
    def encode(self, data: bytes, /, **kwargs: Any) -> str: ...

    @abstractmethod
    def decode(self, encoded: "SequenceBatch" | str, /, **kwargs: Any) -> bytes: ...


class FEC(ABC):
    @abstractmethod
    def encode(self, data: bytes, /, **kwargs: Any) -> Tuple[bytes, dict[str, Any]]: ...

    @abstractmethod
    def decode(self, encoded: bytes, info: dict[str, Any], /, **kwargs: Any) -> Tuple[bytes, int]: ...


class Simulator(ABC):
    @abstractmethod
    def simulate(self, sequence: str | "SequenceBatch") -> str | "SequenceBatch": ...

    def with_profile(self, profile: str) -> "Simulator":
        raise NotImplementedError


class Visualizer(ABC):
    @abstractmethod
    def visualize(self, sequence: str, /, **kwargs: Any) -> Any: ...
