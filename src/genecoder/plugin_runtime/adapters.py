from __future__ import annotations
# ruff: noqa: ANN401

from collections.abc import Callable, Mapping
from typing import Any, Literal, cast
import warnings

from genecoder.plugin_api import Codec, CodecCapability, FEC, FECCapability, Simulator, SimulatorCapability, Visualizer, VisualizerCapability

from .descriptors import PLUGIN_DESCRIPTOR_VERSION, RuntimePluginDescriptor, ValidationContract


def _warn_legacy_map(name: str, kind: str) -> None:
    message = (
        f"Loaded legacy map-style {kind} plugin '{name}'. This is deprecated and will be removed; "
        "migrate to RuntimePluginDescriptor contracts."
    )
    warnings.warn(message, DeprecationWarning, stacklevel=3)


def descriptor_from_legacy_mapping(
    name: str,
    kind: Literal["codec", "fec", "simulator", "visualizer"],
    mapping: Mapping[str, Any],
) -> RuntimePluginDescriptor:
    _warn_legacy_map(name, kind)
    impl = mapping
    if kind == "codec":
        capability = CodecCapability()
        validation = ValidationContract(
            encode_input="bytes",
            encode_output="sequence",
            decode_input="sequence|batch",
            decode_output="bytes",
        )
    elif kind == "fec":
        capability = FECCapability()
        validation = ValidationContract()
    elif kind == "simulator":
        capability = SimulatorCapability()
        validation = ValidationContract()
    else:
        capability = VisualizerCapability()
        validation = ValidationContract()

    return RuntimePluginDescriptor(
        api_version=PLUGIN_DESCRIPTOR_VERSION,
        name=name,
        kind=kind,
        implementation=impl,
        capabilities=capability,
        validation=validation,
        metadata={"legacy_mapping": "true", "interface_version": capability.interface_version},
    )


def descriptor_from_legacy_callable(
    name: str,
    kind: Literal["codec", "fec", "simulator", "visualizer"],
    implementation: object,
) -> RuntimePluginDescriptor:
    if kind == "codec":
        capability = CodecCapability()
        validation = ValidationContract(
            encode_input="bytes",
            encode_output="sequence",
            decode_input="sequence|batch",
            decode_output="bytes",
        )
    elif kind == "fec":
        capability = FECCapability()
        validation = ValidationContract()
    elif kind == "simulator":
        capability = SimulatorCapability()
        validation = ValidationContract()
    else:
        capability = VisualizerCapability()
        validation = ValidationContract()

    return RuntimePluginDescriptor(
        api_version=PLUGIN_DESCRIPTOR_VERSION,
        name=name,
        kind=kind,
        implementation=implementation,
        capabilities=capability,
        validation=validation,
        metadata={"interface_version": capability.interface_version},
    )


def mapping_to_bound_methods(mapping: Mapping[str, Callable[..., Any]], *, kind: str) -> object:
    if kind == "codec":
        encode = mapping.get("encode")
        decode = mapping.get("decode")
        if not callable(encode) or not callable(decode):
            raise TypeError("legacy codec mapping must expose callable encode/decode")

        class LegacyCodecAdapter(Codec):
            def encode(self, data: bytes, /, **kwargs: Any) -> str:
                return cast(Callable[..., str], encode)(data, **kwargs)

            def decode(self, encoded: str, /, **kwargs: Any) -> bytes:
                return cast(Callable[..., bytes], decode)(encoded, **kwargs)

        return LegacyCodecAdapter()

    if kind == "fec":
        encode = mapping.get("encode")
        decode = mapping.get("decode")
        if not callable(encode) or not callable(decode):
            raise TypeError("legacy fec mapping must expose callable encode/decode")

        class LegacyFECAdapter(FEC):
            def encode(self, data: bytes, /, **kwargs: Any) -> tuple[bytes, dict[str, Any]]:
                return cast(Callable[..., tuple[bytes, dict[str, Any]]], encode)(data, **kwargs)

            def decode(self, encoded: bytes, info: dict[str, Any], /, **kwargs: Any) -> tuple[bytes, int]:
                return cast(Callable[..., tuple[bytes, int]], decode)(encoded, info, **kwargs)

        return LegacyFECAdapter()

    if kind == "simulator":
        simulate = mapping.get("simulate")
        if not callable(simulate):
            raise TypeError("legacy simulator mapping must expose callable simulate")

        class LegacySimulatorAdapter(Simulator):
            def simulate(self, sequence: str) -> str:
                return cast(Callable[..., str], simulate)(sequence)

        return LegacySimulatorAdapter()

    visualize = mapping.get("visualize")
    if not callable(visualize):
        raise TypeError("legacy visualizer mapping must expose callable visualize")

    class LegacyVisualizerAdapter(Visualizer):
        def visualize(self, sequence: str, /, **kwargs: Any) -> Any:
            return cast(Callable[..., Any], visualize)(sequence, **kwargs)

    return LegacyVisualizerAdapter()
