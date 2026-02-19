from __future__ import annotations

from dataclasses import dataclass, field
import time
import warnings
from typing import Any, Callable, Literal, Mapping, Protocol, Sequence

from genecoder.constraints.policy import ConstraintPolicy

from genecoder.formats import SequenceBatch

ChannelErrorType = Literal["substitution", "insertion", "deletion", "dropout", "erasure"]



def _get_registries() -> tuple[dict[str, object], dict[str, object]]:
    from genecoder.plugin_runtime.registry import CODEC_REGISTRY, FEC_REGISTRY

    return CODEC_REGISTRY, FEC_REGISTRY


@dataclass(slots=True)
class CodingContext:
    """Per-block context shared across coding layers."""

    block_id: str = "block-0"
    metadata: dict[str, Any] = field(default_factory=dict)
    constraint_policy: ConstraintPolicy | None = None


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


@dataclass(slots=True, frozen=True)
class CodecCapabilities:
    supports_streaming: bool = False
    block_size: int | None = None
    expected_channel_errors: tuple[ChannelErrorType, ...] = ()
    redundancy_model: str = "none"


@dataclass(slots=True, frozen=True)
class FECCapabilities:
    supports_streaming: bool = False
    block_size: int | None = None
    expected_channel_errors: tuple[ChannelErrorType, ...] = ("substitution", "insertion", "deletion")
    redundancy_model: str = "systematic"


@dataclass(slots=True, frozen=True)
class ValidationMetadata:
    encode_input: str = "bytes"
    encode_output: str = "bytes"
    decode_input: str = "bytes"
    decode_output: str = "bytes"


class LayerPluginDescriptor(Protocol):
    name: str
    kind: Literal["codec", "fec"]
    encode_fn: Callable[..., Any]
    decode_fn: Callable[..., Any]
    capabilities: CodecCapabilities | FECCapabilities
    validation: ValidationMetadata


@dataclass(slots=True)
class PluginLayerDescriptor:
    name: str
    kind: Literal["codec", "fec"]
    encode_fn: Callable[..., Any]
    decode_fn: Callable[..., Any]
    capabilities: CodecCapabilities | FECCapabilities
    validation: ValidationMetadata = field(default_factory=ValidationMetadata)
    legacy_source: bool = False

    def __getitem__(self, key: str) -> Callable[..., object] | CodecCapabilities | FECCapabilities | ValidationMetadata:
        if key == "encode":
            return self.encode_fn
        if key == "decode":
            return self.decode_fn
        if key == "capabilities":
            return self.capabilities
        if key == "validation":
            return self.validation
        raise KeyError(key)

    def __setitem__(self, key: str, value: Callable[..., object]) -> None:
        if key == "encode":
            self.encode_fn = value
            return
        if key == "decode":
            self.decode_fn = value
            return
        raise KeyError(key)


@dataclass(slots=True)
class PlanCandidate:
    layer_name: str
    layer_type: Literal["codec", "fec"]
    accepted: bool
    reason: str = ""


@dataclass(slots=True)
class CodingPlan:
    requested_codec: str
    requested_fec: str | None
    selected: list[PluginLayerDescriptor]
    candidates: list[PlanCandidate]
    valid: bool

    def summary(self) -> dict[str, Any]:
        return {
            "requested": {"codec": self.requested_codec, "fec": self.requested_fec},
            "selected": [{"name": layer.name, "type": layer.kind} for layer in self.selected],
            "candidates": [
                {
                    "name": c.layer_name,
                    "type": c.layer_type,
                    "accepted": c.accepted,
                    "reason": c.reason,
                }
                for c in self.candidates
            ],
            "valid": self.valid,
        }


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


def _descriptor_from_registry_entry(name: str, layer_type: Literal["codec", "fec"], entry: object) -> PluginLayerDescriptor:
    if isinstance(entry, PluginLayerDescriptor):
        return entry
    if isinstance(entry, Mapping) and callable(entry.get("encode")) and callable(entry.get("decode")):
        warnings.warn(
            f"Legacy {layer_type} registration for '{name}' is deprecated; register descriptors instead.",
            DeprecationWarning,
            stacklevel=3,
        )
        caps: CodecCapabilities | FECCapabilities
        if layer_type == "codec":
            caps = CodecCapabilities()
        else:
            caps = FECCapabilities()
        return PluginLayerDescriptor(
            name=name,
            kind=layer_type,
            encode_fn=entry["encode"],
            decode_fn=entry["decode"],
            capabilities=caps,
            validation=ValidationMetadata(),
            legacy_source=True,
        )
    raise ValueError(f"Invalid {layer_type} entry for '{name}'")


def _check_compatibility(
    codec_desc: PluginLayerDescriptor,
    fec_desc: PluginLayerDescriptor | None,
    *,
    require_streaming: bool,
    channel_errors: set[str],
) -> list[PlanCandidate]:
    candidates: list[PlanCandidate] = []
    candidates.append(PlanCandidate(codec_desc.name, "codec", True, "codec selected"))

    if require_streaming and not codec_desc.capabilities.supports_streaming:
        candidates[0] = PlanCandidate(codec_desc.name, "codec", False, "codec does not support streaming")

    if fec_desc is None:
        return candidates

    if require_streaming and not fec_desc.capabilities.supports_streaming:
        candidates.append(PlanCandidate(fec_desc.name, "fec", False, "FEC does not support streaming"))
        return candidates

    if codec_desc.capabilities.block_size and fec_desc.capabilities.block_size:
        if codec_desc.capabilities.block_size != fec_desc.capabilities.block_size:
            candidates.append(
                PlanCandidate(
                    fec_desc.name,
                    "fec",
                    False,
                    "block-size mismatch between codec and FEC",
                )
            )
            return candidates

    if channel_errors:
        unsupported = channel_errors - set(fec_desc.capabilities.expected_channel_errors)
        if unsupported:
            candidates.append(
                PlanCandidate(
                    fec_desc.name,
                    "fec",
                    False,
                    f"FEC not designed for channel errors: {', '.join(sorted(unsupported))}",
                )
            )
            return candidates

    candidates.append(PlanCandidate(fec_desc.name, "fec", True, "compatible with codec and channel"))
    return candidates


def plan_stack_from_config(config: Mapping[str, Any], *, constraint_policy: ConstraintPolicy | None = None) -> CodingPlan:
    coding_section = config.get("coding") if isinstance(config.get("coding"), Mapping) else {}
    codec = config.get("codec")
    fec = config.get("fec")
    require_streaming = bool(coding_section.get("streaming")) if isinstance(coding_section, Mapping) else False
    channel_errors = set()
    raw_errors = coding_section.get("channel_errors") if isinstance(coding_section, Mapping) else None
    if isinstance(raw_errors, Sequence) and not isinstance(raw_errors, (str, bytes, bytearray)):
        channel_errors = {str(item).strip().lower() for item in raw_errors if str(item).strip()}

    if not isinstance(codec, str) or not codec:
        raise ValueError("Config must provide either coding.layers or codec")

    codec_registry, fec_registry = _get_registries()
    codec_entry = codec_registry.get(codec)
    if codec_entry is None:
        raise ValueError(f"Unknown codec: {codec}")
    codec_desc = _descriptor_from_registry_entry(codec, "codec", codec_entry)

    fec_desc: PluginLayerDescriptor | None = None
    if isinstance(fec, str) and fec:
        fec_entry = fec_registry.get(fec)
        if fec_entry is None:
            raise ValueError(f"Unknown FEC: {fec}")
        fec_desc = _descriptor_from_registry_entry(fec, "fec", fec_entry)

    candidates = _check_compatibility(
        codec_desc,
        fec_desc,
        require_streaming=require_streaming,
        channel_errors=channel_errors,
    )
    valid = all(c.accepted for c in candidates)
    selected = [codec_desc] if fec_desc is None else [fec_desc, codec_desc]
    if not valid:
        selected = []
    return CodingPlan(
        requested_codec=codec,
        requested_fec=fec if isinstance(fec, str) and fec else None,
        selected=selected,
        candidates=candidates,
        valid=valid,
    )


def compile_legacy_stack(codec: str, fec: str | None, *, constraint_policy: ConstraintPolicy | None = None) -> list[CodingLayer]:
    plan = plan_stack_from_config({"codec": codec, "fec": fec}, constraint_policy=constraint_policy)
    if not plan.valid:
        reason = "; ".join(c.reason for c in plan.candidates if not c.accepted)
        raise ValueError(f"Unable to assemble coding stack: {reason}")
    layers: list[CodingLayer] = []
    for descriptor in plan.selected:
        cls = _layer_adapter(descriptor.name, descriptor.kind)
        layers.append(
            cls(
                name=descriptor.name,
                encode_fn=descriptor.encode_fn,
                decode_fn=descriptor.decode_fn,
            )
        )
    return layers


def compile_stack_from_config(config: Mapping[str, Any], *, constraint_policy: ConstraintPolicy | None = None) -> list[CodingLayer]:
    coding_section = config.get("coding")
    if isinstance(coding_section, Mapping) and isinstance(coding_section.get("layers"), Sequence):
        layer_specs = coding_section["layers"]
        normalized = dict(config)
        codec_name: str | None = None
        fec_name: str | None = None
        for idx, raw in enumerate(layer_specs):
            if not isinstance(raw, Mapping):
                raise ValueError(f"coding.layers[{idx}] must be a mapping")
            layer_type = str(raw.get("type", "")).strip().lower()
            layer_name = str(raw.get("name", "")).strip()
            if layer_type not in {"codec", "fec"}:
                raise ValueError(f"coding.layers[{idx}] has invalid type '{layer_type}'")
            if not layer_name:
                raise ValueError(f"coding.layers[{idx}] is missing layer name")
            if layer_type == "codec":
                if codec_name is not None:
                    raise ValueError("coding.layers must contain exactly one codec layer")
                codec_name = layer_name
            elif fec_name is None:
                fec_name = layer_name
            else:
                raise ValueError("coding.layers supports at most one FEC layer")
        if codec_name is None:
            raise ValueError("coding.layers must contain exactly one codec layer")
        normalized["codec"] = codec_name
        if fec_name:
            normalized["fec"] = fec_name
        plan = plan_stack_from_config(normalized, constraint_policy=constraint_policy)
    else:
        plan = plan_stack_from_config(config, constraint_policy=constraint_policy)

    if not plan.valid:
        reason = "; ".join(c.reason for c in plan.candidates if not c.accepted)
        raise ValueError(f"Unable to assemble coding stack: {reason}")

    compiled: list[CodingLayer] = []
    for descriptor in plan.selected:
        cls = _layer_adapter(descriptor.name, descriptor.kind)
        compiled.append(cls(name=descriptor.name, encode_fn=descriptor.encode_fn, decode_fn=descriptor.decode_fn))
    return compiled


def normalize_stack_metrics(layer_metrics: Sequence[Mapping[str, Any]], sequence: str | None = None) -> dict[str, Any]:
    total_redundancy = 1.0
    total_corrections = 0
    normalized_layers: list[dict[str, Any]] = []
    for idx, item in enumerate(layer_metrics, start=1):
        redundancy = float(item.get("redundancy", 1.0) or 1.0)
        corrections = int(item.get("corrections", 0) or 0)
        total_redundancy *= redundancy
        total_corrections += corrections
        normalized_layers.append(
            {
                "index": int(item.get("index", idx)),
                "name": str(item.get("name", "unknown")),
                "type": str(item.get("type", "unknown")),
                "stage": str(item.get("stage", "unknown")),
                "input_size": int(item.get("input_size", 0) or 0),
                "output_size": int(item.get("output_size", 0) or 0),
                "duration_ms": float(item.get("duration_ms", 0.0) or 0.0),
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


def build_layer_metric(
    *,
    layer_name: str,
    layer_type: str,
    stage: str,
    before_size: int,
    after_size: int,
    started_at: float,
    corrections: int = 0,
) -> dict[str, Any]:
    duration_ms = (time.perf_counter() - started_at) * 1000.0
    ratio_num = float(after_size) if stage == "encode" else float(before_size)
    ratio_den = max(1.0, float(before_size) if stage == "encode" else float(after_size))
    return {
        "name": layer_name,
        "type": layer_type,
        "stage": stage,
        "input_size": before_size,
        "output_size": after_size,
        "duration_ms": duration_ms,
        "redundancy": ratio_num / ratio_den,
        "corrections": int(corrections),
    }


__all__ = [
    "CodingContext",
    "CodingLayer",
    "LayerIO",
    "CodecCapabilities",
    "FECCapabilities",
    "ValidationMetadata",
    "PluginLayerDescriptor",
    "CodingPlan",
    "compile_legacy_stack",
    "compile_stack_from_config",
    "plan_stack_from_config",
    "build_layer_metric",
    "normalize_stack_metrics",
]
