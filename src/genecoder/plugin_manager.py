from __future__ import annotations

from typing import Callable, Dict, Any, Iterable, Mapping, cast
from collections.abc import MutableMapping
from types import ModuleType

import os
import sys
import subprocess
import urllib.request
from urllib.parse import urlparse
import tempfile
from pathlib import Path
import importlib
import re
import inspect

yaml: ModuleType | None
try:  # optional dependency
    import yaml as yaml_module
except Exception:  # pragma: no cover - optional
    yaml = None
else:
    yaml = yaml_module


from importlib.metadata import (
    entry_points,
    EntryPoints,
    version as get_pkg_version,
    PackageNotFoundError,
)
import logging
import pkgutil

from .simulators import SIMULATOR_REGISTRY, register_simulator as _register_simulator
from . import plugin_security
from .api import Codec, FEC, Simulator, Visualizer
import base64
import json


logger = logging.getLogger(__name__)

CODEC_REGISTRY: Dict[str, Dict[str, Callable[..., Any]]] = {}
FEC_REGISTRY: Dict[str, Dict[str, Callable[..., Any]]] = {}
VISUALIZER_REGISTRY: Dict[str, Callable[..., Any]] = {}

PLUGIN_CATALOG: Dict[str, Dict[str, Any]] = {}

_ENTRY_POINT_LOADERS: Dict[str, Dict[str, Callable[[], None]]] = {
    "codec": {},
    "FEC": {},
    "simulator": {},
    "visualizer": {},
}

_ENTRY_POINT_METADATA: Dict[str, Dict[str, Any]] = {}


class _LazyMappingPlugin(MutableMapping[str, Callable[..., Any]]):
    """Proxy mapping that imports entry point plugins on first access."""

    __slots__ = ("_kind", "_name", "_registry", "_fallback", "_loading")

    def __init__(
        self,
        kind: str,
        name: str,
        registry: Dict[str, Any],
        fallback: Mapping[str, Callable[..., Any]] | None = None,
    ) -> None:
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
            _load_pending_entry_point(self._kind, self._name)
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
        mapping = dict(self._resolve())
        mapping[key] = value
        dict.__setitem__(self._registry, self._name, mapping)

    def __delitem__(self, key: str) -> None:
        mapping = dict(self._resolve())
        del mapping[key]
        dict.__setitem__(self._registry, self._name, mapping)

    def __iter__(self):
        return iter(self._resolve())

    def __len__(self) -> int:
        return len(self._resolve())

    def __repr__(self) -> str:  # pragma: no cover - representation helper
        if self._registry.get(self._name) is self:
            return f"<Lazy{self._kind.title()}Plugin {self._name!r}>"
        return repr(self._resolve())


class _LazyVisualizer:
    """Callable proxy that loads the underlying visualizer on demand."""

    __slots__ = ("_name", "_fallback", "_loading")

    def __init__(
        self, name: str, fallback: Callable[..., Any] | None = None
    ) -> None:
        self._name = name
        self._fallback = fallback
        self._loading = False

    def _resolve(self) -> Callable[..., Any]:
        value = VISUALIZER_REGISTRY.get(self._name)
        if value is not self:
            return cast(Callable[..., Any], value)
        if self._loading:
            raise RuntimeError(f"Recursive load for visualizer {self._name}")
        self._loading = True
        try:
            _load_pending_entry_point("visualizer", self._name)
        except Exception:
            if self._fallback is not None:
                VISUALIZER_REGISTRY[self._name] = self._fallback
                return self._fallback
            raise
        finally:
            self._loading = False
        value = VISUALIZER_REGISTRY.get(self._name)
        if value is self:
            if self._fallback is not None:
                VISUALIZER_REGISTRY[self._name] = self._fallback
                return self._fallback
            raise RuntimeError(f"Visualizer {self._name} failed to register")
        return cast(Callable[..., Any], value)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._resolve(), attr)

    def __repr__(self) -> str:  # pragma: no cover - representation helper
        if VISUALIZER_REGISTRY.get(self._name) is self:
            return f"<LazyVisualizer {self._name!r}>"
        return repr(self._resolve())


class _LazySimulator(Simulator):
    """Simulator proxy that loads entry point channels on demand."""

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
            _load_pending_entry_point("simulator", self._name)
        except Exception:
            if self._fallback is not None:
                _register_simulator(self._name, self._fallback)
                return self._fallback
            raise
        finally:
            self._loading = False
        channel = SIMULATOR_REGISTRY.get(self._name)
        if channel is self:
            if self._fallback is not None:
                _register_simulator(self._name, self._fallback)
                return self._fallback
            raise RuntimeError(f"Simulator {self._name} failed to register")
        return cast(Simulator, channel)

    def simulate(self, sequence: str) -> str:
        return self._resolve().simulate(sequence)

    def with_profile(self, profile: str) -> Simulator:
        return self._resolve().with_profile(profile)

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._resolve(), attr)

    def __repr__(self) -> str:  # pragma: no cover - representation helper
        if SIMULATOR_REGISTRY.get(self._name) is self:
            return f"<LazySimulator {self._name!r}>"
        return repr(self._resolve())


def _load_pending_entry_point(kind: str, name: str) -> None:
    loader = _ENTRY_POINT_LOADERS.get(kind, {}).pop(name, None)
    if loader is None:
        return
    loader()


def _entry_point_version(entry_point: Any) -> str:
    dist = getattr(entry_point, "dist", None)
    version = getattr(dist, "version", None)
    if version:
        return str(version)
    module_name = getattr(entry_point, "module", "")
    if module_name:
        root = module_name.split(".")[0]
        try:
            return get_pkg_version(root)
        except PackageNotFoundError:
            pass
    value = getattr(entry_point, "value", "")
    if value:
        root = value.split(":", 1)[0].split(".")[0]
        try:
            return get_pkg_version(root)
        except PackageNotFoundError:
            pass
    return ""


def _record_entry_point_metadata(entry_name: str, kind: str, entry_point: Any) -> None:
    meta = _ENTRY_POINT_METADATA.setdefault(entry_name, {})
    meta.setdefault("entry_name", entry_name)
    meta.setdefault("metadata_name", meta.get("metadata_name") or entry_name)
    version = meta.get("version")
    if not version:
        ep_version = _entry_point_version(entry_point)
        if ep_version:
            meta["version"] = ep_version
    interfaces = meta.setdefault("interfaces", set())
    interfaces.add(kind)
    module_name = getattr(entry_point, "module", None)
    if not module_name:
        value = getattr(entry_point, "value", "")
        module_name = value.split(":", 1)[0]
    if module_name:
        meta.setdefault("module", module_name)


def _update_entry_point_metadata(entry_name: str, module: ModuleType) -> None:
    try:
        meta = _validate_plugin_metadata(getattr(module, "PLUGIN_METADATA", None))
    except Exception as exc:
        logger.warning("Incompatible plugin %s: %s", entry_name, exc)
        return
    cached = _ENTRY_POINT_METADATA.setdefault(entry_name, {})
    cached["entry_name"] = entry_name
    cached["metadata_name"] = meta["name"]
    cached["version"] = meta["version"]
    cached["interfaces"] = set(meta["interfaces"])


def _register_lazy_placeholder(kind: str, name: str) -> None:
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


def _load_entry_point_module(
    entry_point: Any,
    registrar: Callable[..., Any],
    kind: str,
    entry_name: str,
) -> None:
    try:
        module = entry_point.load()
    except Exception as exc:
        logger.warning("Failed to import %s plugin %s: %s", kind, entry_name, exc)
        raise
    _update_entry_point_metadata(entry_name, module)
    register = getattr(module, "register", None)
    if not callable(register):
        logger.warning("Entry point %s missing register()", entry_name)
        return
    try:
        register(registrar)
    except Exception as exc:
        logger.warning("Failed to register %s plugin %s: %s", kind, entry_name, exc)
        raise

_VALID_INTERFACES = {"codec", "FEC", "simulator", "visualizer"}

# re-export for tests
compute_checksum = plugin_security.compute_checksum

_SAFE_PKG_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_SAFE_URL_RE = re.compile(r"^(?:https?|file)://[A-Za-z0-9._~:/?#@!$&'()*+,;=%-]+$")


def _validate_spec(spec: str) -> None:
    """Raise ``ValueError`` if *spec* is not a safe package name or URL."""

    if not spec or re.search(r"[\s;&|`$<>]", spec):
        raise ValueError("Unsafe plugin spec")
    if _SAFE_PKG_RE.fullmatch(spec) or _SAFE_URL_RE.fullmatch(spec):
        return
    raise ValueError("Unsafe plugin spec")


def _check_signature(
    impl: Callable[..., Any], base: Callable[..., Any], *, kind: str, method: str
) -> None:
    """Validate that ``impl`` can accept the parameters of ``base``."""

    base_sig = inspect.signature(base)
    params = list(base_sig.parameters.values())
    if params and params[0].name == "self":
        params = params[1:]
    base_sig = base_sig.replace(parameters=params)

    impl_sig = inspect.signature(impl)

    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params):
        if not any(p.kind == inspect.Parameter.VAR_KEYWORD for p in impl_sig.parameters.values()):
            raise TypeError(f"{kind} {method} must accept **kwargs")

    dummy_args = [
        object()
        for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    dummy_kwargs = {
        p.name: object()
        for p in params
        if p.kind == inspect.Parameter.KEYWORD_ONLY
    }
    try:
        impl_sig.bind(*dummy_args, **dummy_kwargs)
    except TypeError as exc:
        raise TypeError(f"{kind} {method} has incompatible signature: {exc}") from exc


def _coerce_plugin(
    obj: object, expected: type[object], methods: Iterable[str], kind: str
) -> object:
    """Return ``obj`` as an instance of ``expected`` ensuring required methods."""
    if isinstance(obj, type):
        if not issubclass(obj, expected):
            raise TypeError(f"{kind} must subclass {expected.__name__}")
        instance: object = obj()
    else:
        if not isinstance(obj, expected):
            raise TypeError(f"{kind} must subclass {expected.__name__}")
        instance = obj
    for method in methods:
        if not callable(getattr(instance, method, None)):
            raise TypeError(f"{kind} missing required method {method}")
        _check_signature(
            getattr(instance, method), getattr(expected, method), kind=kind, method=method
        )
    return instance


def register_codec(name: str, codec: Codec | type[Codec]) -> None:
    """Register a codec implementation under ``name``.

    If multiple plugins register the same ``name`` the last registration wins.
    Plugins are discovered in the order built-in, entry-point and then local
    modules, allowing user supplied plugins to override bundled ones.
    """

    inst = cast(Any, _coerce_plugin(codec, Codec, ("encode", "decode"), "codec"))
    CODEC_REGISTRY[name] = {"encode": inst.encode, "decode": inst.decode}


def register_fec(name: str, fec: FEC | type[FEC]) -> None:
    """Register a FEC backend under ``name``.

    Later registrations override earlier ones; discovery follows the same
    built-in, entry-point then local order as codecs.
    """

    inst = cast(Any, _coerce_plugin(fec, FEC, ("encode", "decode"), "FEC"))
    FEC_REGISTRY[name] = {"encode": inst.encode, "decode": inst.decode}


def register_simulator(name: str, channel: Simulator | type[Simulator]) -> None:
    """Register a read simulator under ``name``.

    Later registrations with the same ``name`` replace earlier ones.  The
    discovery order mirrors codecs and FEC backends.
    """

    inst = cast(Any, _coerce_plugin(channel, Simulator, ("simulate",), "simulator"))
    _register_simulator(name, inst)


def register_visualizer(name: str, visualizer: Visualizer | type[Visualizer]) -> None:
    """Register a visualizer under ``name``.

    As with other plugin types, later registrations win and discovery order is
    built-in first followed by entry-point and local plugins.
    """

    inst = cast(Any, _coerce_plugin(visualizer, Visualizer, ("visualize",), "visualizer"))
    VISUALIZER_REGISTRY[name] = inst.visualize



def _read_local(path_str: str) -> bytes:
    path = urlparse(path_str).path if path_str.startswith("file://") else path_str
    return Path(path).read_bytes()


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    current_list: list[Dict[str, Any]] | None = None
    current_item: Dict[str, Any] | None = None
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.endswith(":") and not stripped.startswith("- "):
            key = stripped[:-1].strip()
            current_item = None
            current_list = []
            result[key] = current_list
            continue
        if stripped.startswith("- "):
            if current_list is None:
                continue
            current_item = {}
            current_list.append(current_item)
            remainder = stripped[2:].strip()
            if remainder:
                if ":" in remainder:
                    k, v = remainder.split(":", 1)
                    current_item[k.strip()] = v.strip()
            continue
        if current_item is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current_item[key.strip()] = value.strip()
    return result


def _load_registry_mapping(raw: bytes | str, yaml_module: ModuleType | None) -> Dict[str, Any]:
    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    if yaml_module is not None:
        try:
            data = yaml_module.safe_load(text)
        except Exception as exc:
            raise ValueError("Invalid plugin registry YAML") from exc
        if isinstance(data, dict) and data:
            return data
        # fall back to minimal parser if PyYAML returns an empty result
    try:
        data = json.loads(text)
    except Exception:
        data = _parse_simple_yaml(text)
    if not isinstance(data, dict):
        raise ValueError("Invalid plugin registry YAML")
    return data


def _fetch_catalog(url: str, *, allow_network: bool) -> bytes:
    if url.startswith("http://") or url.startswith("https://"):
        if not allow_network:
            msg = (
                "Network access is disabled. Set GENECODER_ALLOW_NETWORK=1 to enable "
                "downloads from the plugin registry specified by GENECODER_PLUGIN_REGISTRY_URL."
            )
            logger.error(msg)
            raise RuntimeError(msg)
        with urllib.request.urlopen(url, timeout=30) as response:
            return cast(bytes, response.read())
    return _read_local(url)


def _install_plugin_spec(
    spec: str,
    *,
    checksum: str | None = None,
    sig_b64: str | None = None,
    version_req: str | None = None,
    package: str | None = None,
    allow_network: bool,
) -> None:
    install_target = spec
    pkg_path = None
    if checksum or sig_b64:
        try:
            path = urlparse(spec).path if spec.startswith("file://") else spec
            if Path(path).exists():
                pkg_bytes = _read_local(spec)
            else:
                if not allow_network:
                    msg = (
                        "Network access is disabled. Set GENECODER_ALLOW_NETWORK=1 to enable "
                        "downloads from the plugin registry specified by GENECODER_PLUGIN_REGISTRY_URL."
                    )
                    logger.error(msg)
                    raise RuntimeError(msg)
                with urllib.request.urlopen(spec, timeout=30) as resp:
                    pkg_bytes = resp.read()
        except Exception as exc:  # pragma: no cover - download error path
            if isinstance(exc, RuntimeError):
                raise
            logger.warning("Failed to download plugin %s: %s", spec, exc)
            raise

        signature = None
        public_key = None
        if sig_b64:
            try:
                signature = base64.b64decode(str(sig_b64), validate=True)
            except Exception:
                logger.error("Invalid signature for plugin %s", spec)
                raise ValueError("Invalid signature")

            key_path = os.getenv("GENECODER_PLUGIN_PUBLIC_KEY")
            if not key_path:
                logger.error("Invalid signature for plugin %s", spec)
                raise ValueError("Invalid signature")
            try:
                public_key = Path(key_path).read_bytes()
            except Exception:
                logger.error("Invalid signature for plugin %s", spec)
                raise ValueError("Invalid signature")

        try:
            digest = plugin_security.compute_checksum(
                pkg_bytes, signature=signature, public_key=public_key
            )
        except Exception:
            logger.error("Invalid signature for plugin %s", spec)
            raise ValueError("Invalid signature")

        if checksum:
            try:
                expected = plugin_security.decode_checksum(str(checksum))
            except ValueError:
                logger.error("Invalid checksum for plugin %s", spec)
                raise ValueError("Invalid checksum")
            if digest != expected:
                logger.error("Checksum mismatch for plugin %s", spec)
                raise ValueError("Checksum mismatch")

        tmp = tempfile.NamedTemporaryFile(delete=False)
        pkg_path = tmp.name
        tmp.write(pkg_bytes)
        tmp.close()
        install_target = pkg_path

    if not allow_network and not (spec.startswith("file://") or Path(spec).exists()):
        msg = (
            "Network access is disabled. Set GENECODER_ALLOW_NETWORK=1 to enable "
            "downloads from the plugin registry specified by GENECODER_PLUGIN_REGISTRY_URL."
        )
        logger.error(msg)
        raise RuntimeError(msg)
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", install_target])
        if version_req:
            pkg_name = str(package or spec).split("==")[0]
            if _SAFE_PKG_RE.fullmatch(pkg_name):
                try:
                    installed_version = get_pkg_version(pkg_name)
                except PackageNotFoundError:
                    logger.error("Version mismatch for plugin %s", pkg_name)
                    raise ValueError("Version mismatch")
                if installed_version != str(version_req):
                    logger.error(
                        "Version mismatch for plugin %s (expected %s, got %s)",
                        pkg_name,
                        version_req,
                        installed_version,
                    )
                    raise ValueError("Version mismatch")
    except Exception as exc:  # pragma: no cover - install error path
        if isinstance(exc, ValueError):
            raise
        logger.warning("Failed to install plugin %s from registry: %s", spec, exc)
    finally:
        if pkg_path is not None:
            try:
                os.unlink(pkg_path)
            except Exception:
                pass


def install_registry_plugins(
    url: str | os.PathLike[str] | None = None,
    *,
    offline: bool | None = None,
    allow_network: bool | None = None,
) -> None:
    """Install plugin packages listed in a YAML registry at ``url``.

    The ``url`` argument may be an HTTP(S) address, a ``file://`` URL or a plain
    filesystem path. Network access is disabled by default; set the
    ``GENECODER_ALLOW_NETWORK`` environment variable or pass ``allow_network=True``
    to enable downloads from the registry specified by
    ``GENECODER_PLUGIN_REGISTRY_URL``. When *offline* is ``True`` or the
    ``GENECODER_OFFLINE`` environment variable is set, network access remains
    disabled regardless of ``allow_network``.
    """

    if isinstance(url, os.PathLike):
        url = os.fspath(url)

    if offline is None:
        offline = bool(os.getenv("GENECODER_OFFLINE"))
    if allow_network is None:
        allow_network = bool(os.getenv("GENECODER_ALLOW_NETWORK"))

    if url is None:
        url = os.getenv("GENECODER_PLUGIN_REGISTRY_URL")
    if not url:
        return

    network_ok = allow_network and not offline

    yaml_module = yaml
    if yaml_module is None:
        try:  # lazy import for environments where PyYAML may be installed later
            import yaml as yaml_module_real
        except Exception:  # pragma: no cover - optional
            logger.warning("YAML support unavailable; skipping registry %s", url)
            return
        else:
            yaml_module = yaml_module_real
            globals()["yaml"] = yaml_module
    if yaml_module is None:  # for type checkers
        logger.warning("YAML support unavailable; skipping registry %s", url)
        return

    try:
        raw = _fetch_catalog(url, allow_network=network_ok)
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise
        logger.warning("Failed to fetch plugin registry %s: %s", url, exc)
        return

    try:
        data = _load_registry_mapping(raw, yaml_module)
    except ValueError as exc:
        logger.warning("Failed to parse plugin registry %s: %s", url, exc)
        raise

    for entry in data.get("packages", []):
        spec = ""
        checksum = None
        sig_b64: str | None = None
        version_req: str | None = None
        package = None
        if isinstance(entry, dict):
            spec = str(entry.get("spec") or entry.get("package") or entry.get("url") or "")
            checksum = entry.get("checksum")
            sig_b64 = entry.get("signature")
            version_req = entry.get("version")
            package = entry.get("package")
        else:
            spec = str(entry)

        if not spec:
            logger.warning("Missing spec for plugin entry %s", entry)
            continue

        _validate_spec(spec)

        if checksum is None and sig_b64 is None:
            raise ValueError("Checksum or signature required")

        _install_plugin_spec(
            spec,
            checksum=checksum,
            sig_b64=sig_b64,
            version_req=version_req,
            package=package,
            allow_network=network_ok,
        )







def _load_and_register(
    items: Iterable[Any],
    registrar: Callable[..., Any],
    kind: str,
    failures: list[str] | None = None,
) -> None:
    """Load ``items`` and call ``register`` on each."""

    for item in items:
        name = getattr(item, "value", getattr(item, "__name__", str(item)))
        try:
            module = (
                item
                if isinstance(item, ModuleType)
                else (
                    item.load()
                    if hasattr(item, "load")
                    else importlib.import_module(name)
                )
            )
        except Exception:  # pragma: no cover - error path
            if failures is not None:
                failures.append(f"{kind}:{name}")
            else:
                logger.warning("Failed to import %s plugin %s", kind, name)
            continue
        register = getattr(module, "register", None)
        if callable(register):
            register(registrar)


def _validate_plugin_metadata(meta: object) -> Dict[str, Any]:
    """Validate plugin metadata structure."""

    if not isinstance(meta, dict):
        raise TypeError("metadata must be a dict")
    name = meta.get("name")
    version = meta.get("version")
    interfaces = meta.get("interfaces")
    if not isinstance(name, str) or not name:
        raise ValueError("missing or invalid name")
    if not isinstance(version, str) or not version:
        raise ValueError("missing or invalid version")
    if not isinstance(interfaces, (list, tuple)) or not interfaces:
        raise ValueError("missing interfaces")
    if any(i not in _VALID_INTERFACES for i in interfaces):
        raise ValueError("unknown interface")
    return {"name": name, "version": version, "interfaces": list(interfaces)}


def _collect_installed_plugins() -> tuple[Dict[str, Dict[str, Any]], list[str]]:
    """Discover installed plugins via entry points and local modules."""

    catalog: Dict[str, Dict[str, Any]] = {}
    failures: list[str] = []

    groups = {
        "genecoder.plugins": "codec",
        "genecoder.fec": "FEC",
        "genecoder.simulators": "simulator",
        "genecoder.visualizers": "visualizer",
    }
    for group, kind in groups.items():
        try:
            entries = entry_points(group=group)
        except TypeError:
            eps = entry_points()
            if hasattr(eps, "select"):
                entries = eps.select(group=group)
            elif isinstance(eps, dict):
                entries = eps.get(group, EntryPoints())
            else:  # pragma: no cover - legacy path
                entries = [ep for ep in eps if getattr(ep, "group", None) == group]
        for ep in entries:
            entry_name = str(getattr(ep, "name", getattr(ep, "value", "")))
            if entry_name:
                _record_entry_point_metadata(entry_name, kind, ep)

    for entry_name, cached in list(_ENTRY_POINT_METADATA.items()):
        if cached.get("metadata_name") and cached.get("metadata_name") != cached.get("entry_name"):
            continue
        module_name = cached.get("module")
        if not module_name:
            continue
        module = sys.modules.get(str(module_name))
        if module is not None:
            _update_entry_point_metadata(entry_name, module)

    for cached in _ENTRY_POINT_METADATA.values():
        entry_name = str(cached.get("entry_name") or "")
        plugin_name = str(cached.get("metadata_name") or entry_name)
        if not plugin_name:
            continue
        interfaces_raw = cached.get("interfaces") or set()
        interfaces = {str(interface) for interface in interfaces_raw}
        version = str(cached.get("version") or "")
        existing = catalog.get(plugin_name)
        if existing:
            combined = set(existing.get("interfaces", [])) | interfaces
            existing["interfaces"] = sorted(combined)
            if not existing.get("version") and version:
                existing["version"] = version
        else:
            catalog[plugin_name] = {
                "version": version,
                "interfaces": sorted(interfaces) if interfaces else [],
            }

    def _handle_module(module: ModuleType, src: str) -> None:
        try:
            meta = _validate_plugin_metadata(getattr(module, "PLUGIN_METADATA", None))
        except Exception as exc:  # pragma: no cover - invalid metadata
            failures.append(src)
            logger.warning("Incompatible plugin %s: %s", src, exc)
            return
        name = meta["name"]
        if name in catalog or name in PLUGIN_CATALOG:
            failures.append(src)
            logger.warning("Duplicate plugin name %s from %s", name, src)
            return
        catalog[name] = {"version": meta["version"], "interfaces": meta["interfaces"]}

    # discover local plugins in a ``plugins`` package
    try:
        import plugins as local_pkg
    except ModuleNotFoundError:
        local_pkg = None

    modules: list[ModuleType] = []
    if local_pkg is not None:
        modules.append(local_pkg)
        if hasattr(local_pkg, "__path__"):
            for _, module_name, _ in pkgutil.iter_modules(local_pkg.__path__):
                try:
                    modules.append(importlib.import_module(f"plugins.{module_name}"))
                except Exception as exc:  # pragma: no cover - import failure path
                    src = f"local:{module_name}"
                    failures.append(src)
                    logger.warning("Failed to import %s: %s", src, exc)
    for mod in modules:
        _handle_module(mod, getattr(mod, "__name__", "local"))

    return catalog, failures


def load_builtin_plugins() -> None:
    """Load built-in plugins and clear existing registries."""

    CODEC_REGISTRY.clear()
    FEC_REGISTRY.clear()
    VISUALIZER_REGISTRY.clear()
    SIMULATOR_REGISTRY.clear()

    builtin = importlib.import_module("genecoder.builtin_plugins")
    if hasattr(builtin, "register_builtin_plugins"):
        builtin.register_builtin_plugins()




def load_entry_point_plugins() -> list[str]:
    """Load plugins registered via Python entry points."""

    failures: list[str] = []
    for loaders in _ENTRY_POINT_LOADERS.values():
        loaders.clear()

    groups: dict[str, tuple[Callable[..., Any], str]] = {
        "genecoder.plugins": (register_codec, "codec"),
        "genecoder.fec": (register_fec, "FEC"),
        "genecoder.simulators": (register_simulator, "simulator"),
        "genecoder.visualizers": (register_visualizer, "visualizer"),
    }

    for group, (registrar, kind) in groups.items():
        try:
            entries = entry_points(group=group)
        except TypeError:
            eps = entry_points()
            if hasattr(eps, "select"):
                entries = eps.select(group=group)
            elif isinstance(eps, dict):
                entries = eps.get(group, EntryPoints())
            else:
                entries = [ep for ep in eps if getattr(ep, "group", None) == group]

        seen: set[str] = set()
        for ep in entries:
            entry_name = str(getattr(ep, "name", getattr(ep, "value", "")))
            if not entry_name:
                failures.append(f"{kind}:unknown")
                continue
            seen.add(entry_name)
            _ENTRY_POINT_LOADERS[kind][entry_name] = (lambda entry=ep, reg=registrar, k=kind, name=entry_name: _load_entry_point_module(entry, reg, k, name))
            _record_entry_point_metadata(entry_name, kind, ep)
            _register_lazy_placeholder(kind, entry_name)

        # prune metadata for removed entry points of this kind
        for meta in _ENTRY_POINT_METADATA.values():
            interfaces = meta.get("interfaces")
            if isinstance(interfaces, set) and kind in interfaces and meta.get("entry_name") not in seen:
                interfaces.discard(kind)

    return failures


def load_local_plugins() -> list[str]:
    """Load plugins from a local ``plugins`` package if present."""

    failures: list[str] = []
    try:
        import plugins
    except ModuleNotFoundError:
        return failures

    if hasattr(plugins, "__path__"):
        for _, module_name, _ in pkgutil.iter_modules(plugins.__path__):
            try:
                module = importlib.import_module(f"plugins.{module_name}")
            except Exception:  # pragma: no cover - error path
                failures.append(f"local:{module_name}")
                continue
            register = getattr(module, "register", None)
            if callable(register):
                register(register_codec)
            register_f = getattr(module, "register_fec", None)
            if callable(register_f):
                register_f(register_fec)
            register_s = getattr(module, "register_simulator", None)
            if callable(register_s):
                register_s(register_simulator)
            register_v = getattr(module, "register_visualizer", None)
            if callable(register_v):
                register_v(register_visualizer)

    register = getattr(plugins, "register", None)
    if callable(register):
        register(register_codec)
    register_f = getattr(plugins, "register_fec", None)
    if callable(register_f):
        register_f(register_fec)
    register_s = getattr(plugins, "register_simulator", None)
    if callable(register_s):
        register_s(register_simulator)
    register_v = getattr(plugins, "register_visualizer", None)
    if callable(register_v):
        register_v(register_visualizer)

    return failures


_initialized = False


def load_plugin_catalog(url: str | None = None) -> None:
    """Populate :data:`PLUGIN_CATALOG` from ``url`` or the environment."""

    if url is None:
        url = os.getenv("GENECODER_PLUGIN_CATALOG_URL")
    catalog: Dict[str, Dict[str, Any]] = {}

    if url:
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                raw = response.read()
        except Exception as exc:
            logger.warning("Failed to fetch plugin catalog %s: %s", url, exc)
            raw = b""

        if raw:
            try:
                data = json.loads(raw.decode("utf-8"))
            except Exception:
                yaml_module = yaml
                if yaml_module is None:
                    logger.warning("Failed to parse plugin catalog %s", url)
                    data = {}
                else:
                    try:
                        data = yaml_module.safe_load(raw) or {}
                    except Exception as exc:
                        logger.warning("Failed to parse plugin catalog %s: %s", url, exc)
                        data = {}
            if isinstance(data, dict):
                signature = data.get("signature")
                scheme = data.get("signature_scheme") or data.get("scheme")
                if signature and not _verify_catalog_signature(raw, signature, padding_scheme=scheme):
                    logger.warning("Invalid catalog signature for %s", url)
                else:
                    plugins_data = data.get("plugins", data.get("entries", {}))
                    if isinstance(plugins_data, list):
                        for entry in plugins_data:
                            if isinstance(entry, dict) and "name" in entry:
                                meta = {k: v for k, v in entry.items() if k != "name"}
                                catalog[str(entry["name"])] = meta
                    elif isinstance(plugins_data, dict):
                        for name, meta in plugins_data.items():
                            if isinstance(meta, dict):
                                catalog[str(name)] = dict(meta)
                    else:
                        logger.warning("Invalid plugin catalog format from %s", url)

    discovered, failures = _collect_installed_plugins()
    for name, meta in discovered.items():
        catalog.setdefault(name, meta)

    PLUGIN_CATALOG.clear()
    PLUGIN_CATALOG.update(catalog)
    if failures:
        logger.warning("Failed to load plugin metadata: %s", ", ".join(failures))


def load_plugins() -> None:
    """Load built-in, entry point and local plugins and fetch catalog entries."""

    load_builtin_plugins()
    failures = load_entry_point_plugins()
    failures.extend(load_local_plugins())
    load_plugin_catalog()
    if failures:
        logger.warning("Failed to import plugins: %s", ", ".join(failures))


def init_plugins() -> None:
    """Initialize plugins once with error handling."""

    global _initialized
    if _initialized:
        return
    try:
        load_plugins()
    except Exception as exc:  # pragma: no cover - unexpected error path
        logger.warning("Failed to load plugins: %s", exc)
    _initialized = True


def _verify_catalog_signature(
    data: bytes, signature_b64: str, *, padding_scheme: str | None = None
) -> bool:
    """Return ``True`` if ``signature_b64`` verifies ``data`` using the public key.

    The key path is read from the ``GENECODER_CATALOG_PUBLIC_KEY`` environment
    variable. ``False`` is returned on any failure.
    """

    key_path = os.getenv("GENECODER_CATALOG_PUBLIC_KEY")
    if not key_path:
        return False

    try:
        public_key = Path(key_path).read_bytes()
    except Exception:
        return False

    try:
        signature = base64.b64decode(signature_b64, validate=True)
    except Exception:
        return False

    try:
        compute_checksum(
            data,
            signature=signature,
            public_key=public_key,
            padding_scheme=padding_scheme or "pkcs1",
        )
    except Exception:
        return False
    return True

