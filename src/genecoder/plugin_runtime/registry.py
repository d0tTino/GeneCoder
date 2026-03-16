from __future__ import annotations

from typing import Any, Callable, cast
import logging

from genecoder.coding.stack import CodecCapabilities, FECCapabilities, PluginLayerDescriptor, ValidationMetadata
from genecoder.plugin_api import Codec, FEC, Simulator, Visualizer
from genecoder.simulators import SIMULATOR_REGISTRY, register_simulator as _register_simulator

from .adapters import descriptor_from_legacy_callable, descriptor_from_legacy_mapping, mapping_to_bound_methods
from .descriptors import PluginLifecycleState, RuntimePluginDescriptor, ValidationResult
from .policy import (
    coerce_plugin,
    enforce_lifecycle_transition,
    validate_runtime_descriptor,
    validation_failure,
    validation_success,
)

logger = logging.getLogger(__name__)

CODEC_REGISTRY: dict[str, PluginLayerDescriptor] = {}
FEC_REGISTRY: dict[str, PluginLayerDescriptor] = {}
VISUALIZER_REGISTRY: dict[str, Callable[..., Any]] = {}
DEPRECATION_NOTICES: list[dict[str, str]] = []
REGISTRATION_STATES: dict[str, PluginLifecycleState] = {}
VALIDATION_RESULTS: dict[str, list[ValidationResult]] = {}


class RuntimeRegistry:
    def __init__(self) -> None:
        self.entry_point_loaders: dict[str, dict[str, Callable[[], None]]] = {
            "codec": {},
            "FEC": {},
            "simulator": {},
            "visualizer": {},
        }

    def load_pending(self, kind: str, name: str) -> None:
        loader = self.entry_point_loaders.get(kind, {}).pop(name, None)
        if loader:
            loader()


RUNTIME_REGISTRY = RuntimeRegistry()


class _LazyLayerDescriptor(PluginLayerDescriptor):
    __slots__ = ("_kind", "_name", "_registry", "_fallback", "_loading")

    def __init__(self, kind: str, name: str, registry: dict[str, PluginLayerDescriptor], fallback: PluginLayerDescriptor | None = None) -> None:
        super().__init__(
            name=name,
            kind=cast(Any, "codec" if kind == "codec" else "fec"),
            encode_fn=lambda *_args, **_kwargs: None,
            decode_fn=lambda *_args, **_kwargs: None,
            capabilities=CodecCapabilities() if kind == "codec" else FECCapabilities(),
        )
        self._kind = kind
        self._name = name
        self._registry = registry
        self._fallback = fallback
        self._loading = False

    def _resolve(self) -> PluginLayerDescriptor:
        value = self._registry.get(self._name)
        if value is not self:
            if value is None:
                raise KeyError(f"{self._kind} plugin {self._name} is missing")
            return value
        if self._loading:
            raise RuntimeError(f"Recursive load for {self._kind} plugin {self._name}")
        self._loading = True
        try:
            RUNTIME_REGISTRY.load_pending(self._kind, self._name)
        except Exception:
            if self._fallback is not None:
                self._registry[self._name] = self._fallback
                return self._fallback
            raise
        finally:
            self._loading = False
        value = self._registry.get(self._name)
        if value is self:
            if self._fallback is not None:
                self._registry[self._name] = self._fallback
                return self._fallback
            raise KeyError(f"{self._kind} plugin {self._name} failed to register")
        if value is None:
            raise KeyError(f"{self._kind} plugin {self._name} is missing")
        return value

    @property
    def encode_fn(self):  # type: ignore[override]
        return self._resolve().encode_fn

    @encode_fn.setter
    def encode_fn(self, value):
        self._resolve().encode_fn = value

    @property
    def decode_fn(self):  # type: ignore[override]
        return self._resolve().decode_fn

    @decode_fn.setter
    def decode_fn(self, value):
        self._resolve().decode_fn = value


class _LazyVisualizer:
    __slots__ = ("_name", "_fallback", "_loading")

    def __init__(self, name: str, fallback: Callable[..., object] | None = None) -> None:
        self._name = name
        self._fallback = fallback
        self._loading = False

    def _resolve(self) -> Callable[..., object]:
        value = VISUALIZER_REGISTRY.get(self._name)
        if value is not self:
            return cast(Callable[..., object], value)
        if self._loading:
            raise RuntimeError(f"Recursive load for visualizer {self._name}")
        self._loading = True
        try:
            RUNTIME_REGISTRY.load_pending("visualizer", self._name)
        except Exception:
            if self._fallback is not None:
                VISUALIZER_REGISTRY[self._name] = self._fallback
                return self._fallback
            raise
        finally:
            self._loading = False
        value = VISUALIZER_REGISTRY.get(self._name)
        if value is self and self._fallback is not None:
            VISUALIZER_REGISTRY[self._name] = self._fallback
            return self._fallback
        return cast(Callable[..., object], value)

    def __call__(self, *args: object, **kwargs: object) -> object:
        return self._resolve()(*args, **kwargs)


class _LazySimulator(Simulator):
    __slots__ = ("_name", "_fallback", "_loading")

    def __init__(self, name: str, fallback: Simulator | None = None) -> None:
        self._name = name
        self._fallback = fallback
        self._loading = False

    def _resolve(self) -> Simulator:
        channel = SIMULATOR_REGISTRY.get(self._name)
        if channel is not self:
            return cast(Simulator, channel)
        if self._loading:
            raise RuntimeError(f"Recursive load for simulator {self._name}")
        self._loading = True
        try:
            RUNTIME_REGISTRY.load_pending("simulator", self._name)
        except Exception:
            if self._fallback is not None:
                _register_simulator(self._name, self._fallback)
                return self._fallback
            raise
        finally:
            self._loading = False
        channel = SIMULATOR_REGISTRY.get(self._name)
        if channel is self and self._fallback is not None:
            _register_simulator(self._name, self._fallback)
            return self._fallback
        return cast(Simulator, channel)

    def simulate(self, sequence: str) -> str:
        return cast(str, self._resolve().simulate(sequence))


def register_lazy_placeholder(kind: str, name: str) -> None:
    if kind == "codec":
        existing = CODEC_REGISTRY.get(name)
        fallback = existing if isinstance(existing, PluginLayerDescriptor) and not isinstance(existing, _LazyLayerDescriptor) else None
        CODEC_REGISTRY[name] = _LazyLayerDescriptor("codec", name, CODEC_REGISTRY, fallback)
    elif kind == "FEC":
        existing = FEC_REGISTRY.get(name)
        fallback = existing if isinstance(existing, PluginLayerDescriptor) and not isinstance(existing, _LazyLayerDescriptor) else None
        FEC_REGISTRY[name] = _LazyLayerDescriptor("FEC", name, FEC_REGISTRY, fallback)
    elif kind == "visualizer":
        existing = VISUALIZER_REGISTRY.get(name)
        fallback = existing if callable(existing) and not isinstance(existing, _LazyVisualizer) else None
        VISUALIZER_REGISTRY[name] = _LazyVisualizer(name, fallback)
    elif kind == "simulator":
        existing = SIMULATOR_REGISTRY.get(name)
        fallback = existing if isinstance(existing, Simulator) and not isinstance(existing, _LazySimulator) else None
        _register_simulator(name, _LazySimulator(name, fallback))


def _set_state(name: str, new_state: PluginLifecycleState) -> None:
    current = REGISTRATION_STATES.get(name, PluginLifecycleState.DISCOVERED)
    if current == new_state:
        return
    REGISTRATION_STATES[name] = enforce_lifecycle_transition(current, new_state)


def _emit_legacy_notice(name: str, kind: str) -> None:
    notice = {
        "type": "deprecation",
        "plugin": name,
        "kind": kind,
        "message": "Legacy registration entry point is deprecated.",
        "migration_hint": "Return RuntimePluginDescriptor via register_plugin() or use descriptor adapters.",
    }
    DEPRECATION_NOTICES.append(notice)
    logger.warning("%s", notice)


def transition_plugin_state(name: str, new_state: PluginLifecycleState) -> PluginLifecycleState:
    _set_state(name, new_state)
    return REGISTRATION_STATES[name]


def evaluate_descriptor_policy(descriptor: RuntimePluginDescriptor) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    try:
        validate_runtime_descriptor(descriptor)
    except Exception as exc:
        results.append(validation_failure("runtime_descriptor", message=str(exc), details={"plugin": descriptor.name}))
    else:
        results.append(validation_success("runtime_descriptor", details={"plugin": descriptor.name, "kind": descriptor.kind}))
    return results


def latest_validation_results(name: str) -> list[ValidationResult]:
    return list(VALIDATION_RESULTS.get(name, []))


def register_plugin(descriptor: RuntimePluginDescriptor) -> None:
    results = evaluate_descriptor_policy(descriptor)
    VALIDATION_RESULTS[descriptor.name] = results
    failures = [result for result in results if not result.success]
    if failures:
        _set_state(descriptor.name, PluginLifecycleState.FAILED)
        raise ValueError(failures[0].message)
    descriptor = validate_runtime_descriptor(descriptor)
    _set_state(descriptor.name, PluginLifecycleState.VALIDATED)

    kind = "fec" if descriptor.kind == "FEC" else descriptor.kind

    implementation = descriptor.implementation
    if isinstance(implementation, dict):
        descriptor = descriptor_from_legacy_mapping(descriptor.name, cast(Any, kind), implementation)
        implementation = mapping_to_bound_methods(cast(Any, implementation), kind=cast(str, kind))

    if kind == "codec":
        inst = cast(Any, coerce_plugin(implementation, Codec, ("encode", "decode"), "codec"))
        CODEC_REGISTRY[descriptor.name] = PluginLayerDescriptor(
            name=descriptor.name,
            kind="codec",
            encode_fn=inst.encode,
            decode_fn=inst.decode,
            capabilities=CodecCapabilities(supports_streaming=getattr(descriptor.capabilities, "supports_streaming", False)),
            validation=ValidationMetadata(
                encode_input=descriptor.validation.encode_input,
                encode_output=descriptor.validation.encode_output,
                decode_input=descriptor.validation.decode_input,
                decode_output=descriptor.validation.decode_output,
            ),
        )
    elif kind == "fec":
        inst = cast(Any, coerce_plugin(implementation, FEC, ("encode", "decode"), "FEC"))
        FEC_REGISTRY[descriptor.name] = PluginLayerDescriptor(
            name=descriptor.name,
            kind="fec",
            encode_fn=inst.encode,
            decode_fn=inst.decode,
            capabilities=FECCapabilities(supports_streaming=getattr(descriptor.capabilities, "supports_streaming", False)),
            validation=ValidationMetadata(
                encode_input=descriptor.validation.encode_input,
                encode_output=descriptor.validation.encode_output,
                decode_input=descriptor.validation.decode_input,
                decode_output=descriptor.validation.decode_output,
            ),
        )
    elif kind == "simulator":
        inst = cast(Any, coerce_plugin(implementation, Simulator, ("simulate",), "simulator"))
        _register_simulator(descriptor.name, inst)
    elif kind == "visualizer":
        inst = cast(Any, coerce_plugin(implementation, Visualizer, ("visualize",), "visualizer"))
        VISUALIZER_REGISTRY[descriptor.name] = inst.visualize
    else:
        raise ValueError(f"Unsupported runtime descriptor kind: {descriptor.kind}")

    _set_state(descriptor.name, PluginLifecycleState.LOADED)




def disable_plugin(name: str) -> PluginLifecycleState:
    if name not in REGISTRATION_STATES:
        raise KeyError(name)
    return transition_plugin_state(name, PluginLifecycleState.DISABLED)


def rollback_plugin(name: str) -> PluginLifecycleState:
    if name not in REGISTRATION_STATES:
        raise KeyError(name)
    return transition_plugin_state(name, PluginLifecycleState.ROLLED_BACK)

def register_codec(name: str, codec: Codec | type[Codec] | dict[str, Any]) -> None:
    _emit_legacy_notice(name, "codec")
    register_plugin(descriptor_from_legacy_callable(name, "codec", codec))


def register_fec(name: str, fec: FEC | type[FEC] | dict[str, Any]) -> None:
    _emit_legacy_notice(name, "fec")
    register_plugin(descriptor_from_legacy_callable(name, "fec", fec))


def register_simulator(name: str, channel: Simulator | type[Simulator] | dict[str, Any]) -> None:
    _emit_legacy_notice(name, "simulator")
    register_plugin(descriptor_from_legacy_callable(name, "simulator", channel))


def register_visualizer(name: str, visualizer: Visualizer | type[Visualizer] | dict[str, Any]) -> None:
    _emit_legacy_notice(name, "visualizer")
    register_plugin(descriptor_from_legacy_callable(name, "visualizer", visualizer))
