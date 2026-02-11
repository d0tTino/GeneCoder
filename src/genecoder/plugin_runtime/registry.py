from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any, Callable, cast

from genecoder.plugin_api import Codec, FEC, Simulator, Visualizer
from genecoder.simulators import SIMULATOR_REGISTRY, register_simulator as _register_simulator

from .policy import coerce_plugin

CODEC_REGISTRY: dict[str, dict[str, Callable[..., Any]]] = {}
FEC_REGISTRY: dict[str, dict[str, Callable[..., Any]]] = {}
VISUALIZER_REGISTRY: dict[str, Callable[..., Any]] = {}


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


class _LazyMappingPlugin(MutableMapping[str, Callable[..., Any]]):
    __slots__ = ("_kind", "_name", "_registry", "_fallback", "_loading")

    def __init__(self, kind: str, name: str, registry: dict[str, Any], fallback: Mapping[str, Callable[..., Any]] | None = None) -> None:
        self._kind = kind
        self._name = name
        self._registry = registry
        self._fallback = fallback
        self._loading = False

    def _resolve(self) -> Mapping[str, Callable[..., Any]]:
        value = self._registry.get(self._name)
        if value is not self:
            return cast(Mapping[str, Callable[..., Any]], value)
        if self._loading:
            raise RuntimeError(f"Recursive load for {self._kind} plugin {self._name}")
        self._loading = True
        try:
            RUNTIME_REGISTRY.load_pending(self._kind, self._name)
        except Exception:
            if self._fallback is not None:
                new_map = dict(self._fallback)
                dict.__setitem__(self._registry, self._name, new_map)
                return new_map
            raise
        finally:
            self._loading = False
        value = self._registry.get(self._name)
        if value is self:
            if self._fallback is not None:
                new_map = dict(self._fallback)
                dict.__setitem__(self._registry, self._name, new_map)
                return new_map
            raise KeyError(f"{self._kind} plugin {self._name} failed to register")
        return cast(Mapping[str, Callable[..., Any]], value)

    def __getitem__(self, key: str) -> Callable[..., Any]:
        return self._resolve()[key]

    def __setitem__(self, key: str, value: Callable[..., Any]) -> None:
        m = dict(self._resolve())
        m[key] = value
        dict.__setitem__(self._registry, self._name, m)

    def __delitem__(self, key: str) -> None:
        m = dict(self._resolve())
        del m[key]
        dict.__setitem__(self._registry, self._name, m)

    def __iter__(self):
        return iter(self._resolve())

    def __len__(self) -> int:
        return len(self._resolve())


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
        return self._resolve().simulate(sequence)


def register_lazy_placeholder(kind: str, name: str) -> None:
    if kind == "codec":
        existing = CODEC_REGISTRY.get(name)
        fallback = existing if isinstance(existing, Mapping) and not isinstance(existing, _LazyMappingPlugin) else None
        CODEC_REGISTRY[name] = _LazyMappingPlugin("codec", name, CODEC_REGISTRY, fallback)
    elif kind == "FEC":
        existing = FEC_REGISTRY.get(name)
        fallback = existing if isinstance(existing, Mapping) and not isinstance(existing, _LazyMappingPlugin) else None
        FEC_REGISTRY[name] = _LazyMappingPlugin("FEC", name, FEC_REGISTRY, fallback)
    elif kind == "visualizer":
        existing = VISUALIZER_REGISTRY.get(name)
        fallback = existing if callable(existing) and not isinstance(existing, _LazyVisualizer) else None
        VISUALIZER_REGISTRY[name] = _LazyVisualizer(name, fallback)
    elif kind == "simulator":
        existing = SIMULATOR_REGISTRY.get(name)
        fallback = existing if isinstance(existing, Simulator) and not isinstance(existing, _LazySimulator) else None
        _register_simulator(name, _LazySimulator(name, fallback))


def register_codec(name: str, codec: Codec | type[Codec]) -> None:
    inst = cast(Any, coerce_plugin(codec, Codec, ("encode", "decode"), "codec"))
    CODEC_REGISTRY[name] = {"encode": inst.encode, "decode": inst.decode}


def register_fec(name: str, fec: FEC | type[FEC]) -> None:
    inst = cast(Any, coerce_plugin(fec, FEC, ("encode", "decode"), "FEC"))
    FEC_REGISTRY[name] = {"encode": inst.encode, "decode": inst.decode}


def register_simulator(name: str, channel: Simulator | type[Simulator]) -> None:
    inst = cast(Any, coerce_plugin(channel, Simulator, ("simulate",), "simulator"))
    _register_simulator(name, inst)


def register_visualizer(name: str, visualizer: Visualizer | type[Visualizer]) -> None:
    inst = cast(Any, coerce_plugin(visualizer, Visualizer, ("visualize",), "visualizer"))
    VISUALIZER_REGISTRY[name] = inst.visualize
