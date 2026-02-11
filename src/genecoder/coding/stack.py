from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, Sequence

from genecoder.formats import SequenceBatch
from genecoder.plugin_manager import CODEC_REGISTRY, FEC_REGISTRY


@dataclass(slots=True)
class CodingContext:
    """Per-block context shared across coding layers."""

    block_id: str = "block-0"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LayerIO:
    """Standardized payload and metadata emitted by each layer."""

    payload: bytes | str | SequenceBatch
    metadata: dict[str, Any] = field(default_factory=dict)


class CodingLayer(Protocol):
    """Typed contract for block-level coding layers."""

    name: str

    def encode_block(self, block: bytes | str | SequenceBatch, context: CodingContext) -> LayerIO:
        ...

    def decode_block(self, block: bytes | str | SequenceBatch, context: CodingContext) -> LayerIO:
        ...


@dataclass(slots=True)
class GenericCodecLayer:
    name: str
    encode_fn: Callable[..., Any]
    decode_fn: Callable[..., Any]

    def encode_block(self, block: bytes | str | SequenceBatch, context: CodingContext) -> LayerIO:
        if not isinstance(block, (bytes, bytearray)):
            raise TypeError(f"Codec layer '{self.name}' expects byte payloads on encode")
        encoded = self.encode_fn(bytes(block))
        return LayerIO(payload=encoded)

    def decode_block(self, block: bytes | str | SequenceBatch, context: CodingContext) -> LayerIO:
        if isinstance(block, SequenceBatch):
            try:
                decoded = self.decode_fn(
                    block,
                    batch_metadata=dict(block.metadata),
                    oligo_metadata=[dict(ol.metadata) for ol in block.oligos],
                )
            except TypeError:
                decoded = self.decode_fn(block.primary_sequence())
        elif isinstance(block, str):
            decoded = self.decode_fn(block)
        else:
            raise TypeError(f"Codec layer '{self.name}' expects sequence payloads on decode")
        return LayerIO(payload=bytes(decoded))


@dataclass(slots=True)
class GenericFECLayer:
    name: str
    encode_fn: Callable[..., Any]
    decode_fn: Callable[..., Any]

    def encode_block(self, block: bytes | str | SequenceBatch, context: CodingContext) -> LayerIO:
        if not isinstance(block, (bytes, bytearray)):
            raise TypeError(f"FEC layer '{self.name}' expects byte payloads")
        encoded, info = self.encode_fn(bytes(block))
        return LayerIO(payload=bytes(encoded), metadata={"fec_info": dict(info)})

    def decode_block(self, block: bytes | str | SequenceBatch, context: CodingContext) -> LayerIO:
        if not isinstance(block, (bytes, bytearray)):
            raise TypeError(f"FEC layer '{self.name}' expects byte payloads")
        info = context.metadata.get("layer_info", {}).get(self.name, {})
        decoded, corrected = self.decode_fn(bytes(block), info)
        return LayerIO(payload=bytes(decoded), metadata={"corrections": int(corrected)})


# Explicit adapters for legacy modules requested in migration plan.
class ReedSolomonLayer(GenericFECLayer):
    pass


class FountainLayer(GenericFECLayer):
    pass


class HammingLayer(GenericFECLayer):
    pass


class LDPCLayer(GenericFECLayer):
    pass


class EncodersLayer(GenericCodecLayer):
    pass


def _layer_adapter(name: str, layer_type: str) -> type[GenericCodecLayer] | type[GenericFECLayer]:
    if layer_type == "fec":
        if name == "reed_solomon":
            return ReedSolomonLayer
        if name == "fountain":
            return FountainLayer
        if name == "hamming_7_4":
            return HammingLayer
        if name == "ldpc":
            return LDPCLayer
        return GenericFECLayer
    return EncodersLayer


def compile_legacy_stack(codec: str, fec: str | None) -> list[CodingLayer]:
    """Compile legacy codec/FEC options into ordered coding layers."""

    layers: list[CodingLayer] = []
    if fec:
        fec_entry = FEC_REGISTRY.get(fec)
        if fec_entry is None:
            raise ValueError(f"Unknown FEC: {fec}")
        fec_cls = _layer_adapter(fec, "fec")
        layers.append(fec_cls(name=fec, encode_fn=fec_entry["encode"], decode_fn=fec_entry["decode"]))

    codec_entry = CODEC_REGISTRY.get(codec)
    if codec_entry is None:
        raise ValueError(f"Unknown codec: {codec}")
    codec_cls = _layer_adapter(codec, "codec")
    layers.append(codec_cls(name=codec, encode_fn=codec_entry["encode"], decode_fn=codec_entry["decode"]))
    return layers


def compile_stack_from_config(config: Mapping[str, Any]) -> list[CodingLayer]:
    """Compile declarative config into layer stack.

    Supports either:
    - ``{"coding": {"layers": [{"type": "fec"|"codec", "name": ...}]}}``
    - legacy ``{"codec": ..., "fec": ...}``
    """

    coding_section = config.get("coding")
    if isinstance(coding_section, Mapping) and isinstance(coding_section.get("layers"), Sequence):
        layer_specs = coding_section["layers"]
        compiled: list[CodingLayer] = []
        for idx, raw in enumerate(layer_specs):
            if not isinstance(raw, Mapping):
                raise ValueError(f"coding.layers[{idx}] must be a mapping")
            layer_type = str(raw.get("type", "")).strip().lower()
            layer_name = str(raw.get("name", "")).strip()
            if layer_type not in {"codec", "fec"}:
                raise ValueError(f"coding.layers[{idx}] has invalid type '{layer_type}'")
            if not layer_name:
                raise ValueError(f"coding.layers[{idx}] is missing layer name")
            registry = CODEC_REGISTRY if layer_type == "codec" else FEC_REGISTRY
            entry = registry.get(layer_name)
            if entry is None:
                raise ValueError(f"Unknown {layer_type} layer '{layer_name}'")
            cls = _layer_adapter(layer_name, layer_type)
            compiled.append(cls(name=layer_name, encode_fn=entry["encode"], decode_fn=entry["decode"]))
        if not compiled:
            raise ValueError("coding.layers cannot be empty")
        if sum(1 for layer in compiled if isinstance(layer, GenericCodecLayer)) != 1:
            raise ValueError("coding.layers must contain exactly one codec layer")
        return compiled

    codec = config.get("codec")
    if not isinstance(codec, str) or not codec:
        raise ValueError("Config must provide either coding.layers or codec")
    fec = config.get("fec")
    return compile_legacy_stack(codec, fec if isinstance(fec, str) else None)


def normalize_stack_metrics(layer_metrics: Sequence[Mapping[str, Any]], sequence: str | None = None) -> dict[str, Any]:
    """Normalize per-layer metrics for downstream reporting."""

    total_redundancy = 1.0
    total_corrections = 0
    normalized_layers: list[dict[str, Any]] = []
    for item in layer_metrics:
        redundancy = float(item.get("redundancy", 1.0) or 1.0)
        corrections = int(item.get("corrections", 0) or 0)
        total_redundancy *= redundancy
        total_corrections += corrections
        normalized_layers.append(
            {
                "name": str(item.get("name", "unknown")),
                "type": str(item.get("type", "unknown")),
                "redundancy": redundancy,
                "corrections": corrections,
            }
        )

    bits_per_nt = None
    if sequence:
        bits_per_nt = (len(sequence) * 2.0)
        bits_per_nt = (1.0 / total_redundancy) if bits_per_nt > 0 else None

    return {
        "layers": normalized_layers,
        "total_redundancy": total_redundancy,
        "total_corrections": total_corrections,
        "effective_bits_per_nt": bits_per_nt,
    }


__all__ = [
    "CodingContext",
    "CodingLayer",
    "LayerIO",
    "compile_legacy_stack",
    "compile_stack_from_config",
    "normalize_stack_metrics",
]
