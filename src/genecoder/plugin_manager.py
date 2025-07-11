from __future__ import annotations

from typing import Callable, Dict, Any, Iterable
from types import ModuleType
import os
import sys
import subprocess
import tempfile
import urllib.request
from urllib.parse import urlparse
import importlib
import base64
from pathlib import Path

_yaml: Any
try:  # pragma: no cover - import is trivial
    _yaml = importlib.import_module("yaml")
except Exception:  # pragma: no cover - optional dependency
    _yaml = None
yaml: Any | None = _yaml

from .channels.base import BaseChannel
from importlib.metadata import entry_points, EntryPoints
import logging
import pkgutil

from .simulators import SIMULATOR_REGISTRY, register_simulator as _register_simulator
from .plugin_security import compute_checksum, verify_signature

logger = logging.getLogger(__name__)

CODEC_REGISTRY: Dict[str, Dict[str, Callable[..., Any]]] = {}
FEC_REGISTRY: Dict[str, Dict[str, Callable[..., Any]]] = {}
PLUGIN_CATALOG: Dict[str, Dict[str, Any]] = {}


def register_codec(
    name: str, encode: Callable[..., Any], decode: Callable[..., Any]
) -> None:
    """Register a codec implementation under ``name``."""
    CODEC_REGISTRY[name] = {"encode": encode, "decode": decode}


def register_fec(
    name: str, encode: Callable[..., Any], decode: Callable[..., Any]
) -> None:
    """Register a FEC backend under ``name``."""
    FEC_REGISTRY[name] = {"encode": encode, "decode": decode}


def register_simulator(name: str, channel: BaseChannel) -> None:
    """Register a read simulator under ``name``."""
    _register_simulator(name, channel)


def _verify_catalog_signature(data: bytes, signature: str) -> bool:
    """Return ``True`` if ``signature`` verifies ``data`` using a public key."""

    key_path = os.getenv("GENECODER_CATALOG_PUBLIC_KEY")
    if not key_path:
        return False

    try:
        sig_bytes = base64.b64decode(signature)
        pubkey = Path(key_path).read_bytes()
    except Exception:
        return False

    try:
        compute_checksum(data, signature=sig_bytes, public_key=pubkey)
    except Exception:
        return False

    return True


def _install_registry_plugins(url: str) -> None:
    """Install plugin packages listed in a YAML registry at ``url``."""

    if yaml is None:  # pragma: no cover - optional dependency missing
        logger.warning(
            "YAML support unavailable, skipping plugin registry %s. "
            "Install PyYAML to enable plugin catalogs.",
            url,
        )
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
        with urllib.request.urlopen(url) as response:
            data = yaml.safe_load(response.read()) or {}
    except Exception as exc:  # pragma: no cover - network error path
        logger.warning("Failed to fetch plugin registry %s: %s", url, exc)
        return

    for entry in data.get("packages", []):
        if isinstance(entry, dict):
            spec = str(
                entry.get("spec") or entry.get("package") or entry.get("url") or ""
            )
            checksum = str(entry.get("checksum", ""))
            sig_b64 = entry.get("signature")
            if not isinstance(sig_b64, str):
                raise ValueError(f"Missing signature for plugin entry {entry}")
            try:
                signature = base64.b64decode(sig_b64)
            except Exception as exc:
                raise ValueError(
                    f"Invalid signature for plugin entry {entry}") from exc
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
            with urllib.request.urlopen(spec) as resp:
                pkg_bytes = resp.read()
        except Exception as exc:  # pragma: no cover - download error path
            logger.warning("Failed to download plugin %s: %s", spec, exc)
            continue

        if signature is not None:
            if pubkey is None:
                logger.warning(
                    "No public key configured for signed plugin %s", spec
                )
                continue
            try:
                digest = compute_checksum(
                    pkg_bytes, signature=signature, public_key=pubkey
                )
            except Exception as exc:
                raise ValueError(
                    f"Invalid signature for plugin {spec}: {exc}") from exc
        else:
            digest = compute_checksum(pkg_bytes)

        if digest != checksum:
            logger.warning("Checksum mismatch for plugin %s", spec)
            continue

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


def _fetch_catalog(url: str) -> None:
    """Fetch plugin catalogue from ``url`` and store in ``PLUGIN_CATALOG``."""

    if yaml is None:  # pragma: no cover - optional dependency missing
        logger.warning(
            "YAML support unavailable, skipping plugin catalog %s. "
            "Install PyYAML to enable plugin catalogs.",
            url,
        )
        return

    try:
        with urllib.request.urlopen(url) as response:
            raw = response.read()
        data = yaml.safe_load(raw) or {}
    except Exception as exc:  # pragma: no cover - network error path
        logger.warning("Failed to fetch plugin catalog %s: %s", url, exc)
        return

    sig = data.get("signature")
    if sig:
        try:
            if not _verify_catalog_signature(raw, str(sig)):
                logger.warning("Invalid catalog signature for %s", url)
                return
        except Exception as exc:  # pragma: no cover - signature error path
            logger.warning("Invalid catalog signature for %s: %s", url, exc)
            return

    PLUGIN_CATALOG.clear()
    allow_unsigned = os.getenv("GENECODER_ALLOW_UNSIGNED_PLUGINS") == "1"
    for entry in data.get("plugins", []):
        name = str(entry.get("name", ""))
        if not name:
            continue
        checksum = entry.get("checksum")
        if not checksum:
            logger.error("Missing checksum for plugin %s", name)
            continue
        signature = entry.get("signature")
        if not signature:
            logger.error("Missing signature for plugin %s", name)
            if not allow_unsigned:
                continue
            signature = ""

        PLUGIN_CATALOG[name] = {
            "version": str(entry.get("version", "")),
            "url": str(entry.get("url", "")),
            "description": str(entry.get("description", "")),
            "checksum": str(checksum),
            "signature": str(signature),
            "author": str(entry.get("author", "")),
            "stars": entry.get("stars", 0),
        }


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


def fetch_plugin_catalog() -> None:
    """Fetch plugin catalog from :envvar:`GENECODER_PLUGIN_CATALOG_URL`."""

    catalog_url = os.getenv("GENECODER_PLUGIN_CATALOG_URL")
    if catalog_url:
        _fetch_catalog(catalog_url)
    else:
        PLUGIN_CATALOG.clear()


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


def load_plugins() -> None:
    """Load built-in, entry point and local plugins and fetch catalog entries."""

    load_builtin_plugins()
    fetch_plugin_catalog()
    failures = load_entry_point_plugins()
    failures.extend(load_local_plugins())
    if failures:
        logger.warning("Failed to import plugins: %s", ", ".join(failures))
