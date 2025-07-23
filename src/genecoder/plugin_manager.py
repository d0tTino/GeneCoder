from __future__ import annotations

from typing import Callable, Dict, Any, Iterable
from types import ModuleType

import os
import sys
import subprocess
import tempfile
import urllib.request
from urllib.parse import urlparse
from pathlib import Path
import importlib
from types import ModuleType

yaml: ModuleType | None
try:  # optional dependency
    import yaml as yaml_module
except Exception:  # pragma: no cover - optional
    yaml = None
else:
    yaml = yaml_module


from importlib.metadata import entry_points, EntryPoints
import logging
import pkgutil

from .simulators import SIMULATOR_REGISTRY, register_simulator as _register_simulator
from .plugin_security import (
    compute_checksum as _compute_checksum,
    verify_signature as _verify_signature,
)
from .plugin_checks import decode_signature, verify_package
import base64


logger = logging.getLogger(__name__)

CODEC_REGISTRY: Dict[str, Dict[str, Callable[..., Any]]] = {}
FEC_REGISTRY: Dict[str, Dict[str, Callable[..., Any]]] = {}
PLUGIN_CATALOG: Dict[str, Dict[str, Any]] = {}

# re-export for tests
verify_signature = _verify_signature
compute_checksum = _compute_checksum


from .api import Codec, FEC, Simulator


def register_codec(name: str, codec: Codec | type[Codec]) -> None:
    """Register a codec implementation under ``name``."""

    if isinstance(codec, type):
        if not issubclass(codec, Codec):
            raise TypeError("codec must subclass Codec")
        inst = codec()
    else:
        if not isinstance(codec, Codec):
            raise TypeError("codec must subclass Codec")
        inst = codec

    CODEC_REGISTRY[name] = {"encode": inst.encode, "decode": inst.decode}


def register_fec(name: str, fec: FEC | type[FEC]) -> None:
    """Register a FEC backend under ``name``."""

    if isinstance(fec, type):
        if not issubclass(fec, FEC):
            raise TypeError("FEC must subclass FEC")
        inst = fec()
    else:
        if not isinstance(fec, FEC):
            raise TypeError("FEC must subclass FEC")
        inst = fec

    FEC_REGISTRY[name] = {"encode": inst.encode, "decode": inst.decode}


def register_simulator(name: str, channel: Simulator) -> None:
    """Register a read simulator under ``name``."""

    if not isinstance(channel, Simulator):
        raise TypeError("simulator must subclass Simulator")

    _register_simulator(name, channel)






def _install_registry_plugins(url: str) -> None:
    """Install plugin packages listed in a YAML registry at ``url``."""

    if yaml is None:
        logger.warning("YAML support unavailable; skipping registry %s", url)
        return

    key_path = os.getenv("GENECODER_PLUGIN_PUBLIC_KEY")
    pubkey: bytes | None = None
    if key_path:
        try:
            pubkey = Path(key_path).read_bytes()
        except Exception:  # pragma: no cover - filesystem error path
            logger.warning("Failed to read public key %s", key_path)
            pubkey = None

    if urlparse(url).scheme != "https":
        logger.warning("Insecure plugin registry URL %s", url)
        return

    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            raw = response.read()
    except Exception as exc:  # pragma: no cover - network error path
        logger.warning("Failed to fetch plugin registry %s: %s", url, exc)
        return

    try:
        data = yaml.safe_load(raw) or {}
    except Exception as exc:
        logger.warning("Failed to parse plugin registry %s: %s", url, exc)
        raise ValueError("Invalid plugin registry YAML") from exc

    for entry in data.get("packages", []):
        if isinstance(entry, dict):
            spec = str(
                entry.get("spec") or entry.get("package") or entry.get("url") or ""
            )
            checksum = str(entry.get("checksum", ""))
            sig_b64 = entry.get("signature")
            if not isinstance(sig_b64, str):
                msg = f"Missing signature for plugin entry {entry}"
                logger.error(msg)
                raise ValueError(msg)
            try:
                signature = decode_signature(sig_b64)
            except ValueError as exc:
                msg = f"Invalid signature for plugin entry {entry}"
                logger.error(msg)
                raise ValueError(msg) from exc
        else:
            logger.warning("Missing checksum for plugin entry %s", entry)
            continue

        if not spec or not checksum:
            logger.warning("Incomplete plugin entry in registry: %s", entry)
            continue

        scheme = urlparse(spec).scheme
        if scheme not in {"https", "file"}:
            logger.warning("Insecure plugin URL %s", spec)
            continue

        try:
            with urllib.request.urlopen(spec, timeout=30) as resp:
                pkg_bytes = resp.read()
        except Exception as exc:  # pragma: no cover - download error path
            logger.warning("Failed to download plugin %s: %s", spec, exc)
            continue

        try:
            digest = verify_package(
                pkg_bytes,
                checksum=checksum,
                signature=signature,
                public_key=pubkey,
                compute_fn=compute_checksum,
            )
        except ValueError as exc:
            if str(exc) == "Checksum mismatch":
                logger.warning("Checksum mismatch for plugin %s", spec)
                continue
            msg = f"Invalid signature for plugin {spec}: {exc}"
            logger.error(msg)
            raise ValueError(msg) from exc

        tmp_file = None
        req_file = None
        try:
            suffix = os.path.splitext(urlparse(spec).path)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(pkg_bytes)
                tmp_file = tmp.name

            with tempfile.NamedTemporaryFile("w", delete=False) as req:
                req.write(f"{tmp_file} --hash=sha256:{digest}\n")
                req_file = req.name

            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--require-hashes",
                    "-r",
                    req_file,
                ]
            )
        except Exception as exc:  # pragma: no cover - install error path
            logger.warning("Failed to install plugin %s from registry: %s", spec, exc)
        finally:
            for path in (tmp_file, req_file):
                if path:
                    try:
                        os.unlink(path)
                    except Exception:
                        pass


def install_registry_plugins(url: str | None = None) -> None:
    """Install packages from a registry URL or :envvar:`GENECODER_PLUGIN_REGISTRY_URL`."""
    if url is None:
        url = os.getenv("GENECODER_PLUGIN_REGISTRY_URL")
    if not url:
        return
    _install_registry_plugins(url)


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


def load_builtin_plugins() -> None:
    """Load built-in plugins and clear existing registries."""

    CODEC_REGISTRY.clear()
    FEC_REGISTRY.clear()
    SIMULATOR_REGISTRY.clear()

    builtin = importlib.import_module("genecoder.builtin_plugins")
    if hasattr(builtin, "register_builtin_plugins"):
        builtin.register_builtin_plugins()




def load_entry_point_plugins() -> list[str]:
    """Load plugins registered via Python entry points."""

    failures: list[str] = []
    groups: dict[str, tuple[Callable[..., Any], str]] = {
        "genecoder.plugins": (register_codec, "codec"),
        "genecoder.fec": (register_fec, "FEC"),
        "genecoder.simulators": (register_simulator, "simulator"),
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
        _load_and_register(entries, registrar, kind, failures)

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

    register = getattr(plugins, "register", None)
    if callable(register):
        register(register_codec)
    register_f = getattr(plugins, "register_fec", None)
    if callable(register_f):
        register_f(register_fec)
    register_s = getattr(plugins, "register_simulator", None)
    if callable(register_s):
        register_s(register_simulator)

    return failures


_initialized = False


def load_plugins() -> None:
    """Load built-in, entry point and local plugins and fetch catalog entries."""

    load_builtin_plugins()
    failures = load_entry_point_plugins()
    failures.extend(load_local_plugins())
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


def _verify_catalog_signature(data: bytes, signature_b64: str) -> bool:
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
        compute_checksum(data, signature=signature, public_key=public_key)
    except Exception:
        return False
    return True

