from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import urllib.request
import urllib
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, Protocol, cast
from urllib.parse import urlparse

from genecoder import plugin_security
from genecoder.plugin_runtime.descriptors import PluginDescriptor, PluginLifecycleState
from genecoder.plugin_runtime.policy import validate_registry_license, validate_spec

logger = logging.getLogger(__name__)

PLUGIN_LOCK: list[dict[str, str]] = []


class PluginInstaller(Protocol):
    def install(self, target: str) -> None: ...


class PipPluginInstaller:
    def install(self, target: str) -> None:
        subprocess.check_call([sys.executable, "-m", "pip", "install", target])


def _read_local(path_str: str) -> bytes:
    path = urlparse(path_str).path if path_str.startswith("file://") else path_str
    return Path(path).read_bytes()


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_list: list[dict[str, Any]] | None = None
    current_item: dict[str, Any] | None = None
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
            if remainder and ":" in remainder:
                k, v = remainder.split(":", 1)
                current_item[k.strip()] = v.strip()
            continue
        if current_item is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current_item[key.strip()] = value.strip()
    return result


def load_registry_mapping(raw: bytes | str, yaml_module: ModuleType | None) -> dict[str, Any]:
    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    if yaml_module is not None:
        try:
            data = yaml_module.safe_load(text)
        except Exception as exc:
            raise ValueError("Invalid plugin registry YAML") from exc
        if isinstance(data, dict) and data:
            return data
    try:
        data = json.loads(text)
    except Exception:
        data = _parse_simple_yaml(text)
    if not isinstance(data, dict):
        raise ValueError("Invalid plugin registry YAML")
    return data


def fetch_catalog(url: str, *, allow_network: bool) -> bytes:
    if url.startswith("http://") or url.startswith("https://"):
        if not allow_network:
            msg = (
                "Network access is disabled. Set GENECODER_ALLOW_NETWORK=1 to enable "
                "downloads from the plugin registry specified by GENECODER_PLUGIN_REGISTRY_URL."
            )
            raise RuntimeError(msg)
        with urllib.request.urlopen(url, timeout=30) as response:
            return cast(bytes, response.read())
    return _read_local(url)


def _download_plugin_bytes(spec: str, *, allow_network: bool) -> bytes:
    path = urlparse(spec).path if spec.startswith("file://") else spec
    if Path(path).exists():
        return _read_local(spec)
    if not allow_network:
        raise RuntimeError(
            "Network access is disabled. Set GENECODER_ALLOW_NETWORK=1 to enable "
            "downloads from the plugin registry specified by GENECODER_PLUGIN_REGISTRY_URL."
        )
    with urllib.request.urlopen(spec, timeout=30) as resp:
        return resp.read()


def _verify_payload(payload: bytes, *, checksum: str, signature: str) -> None:
    import base64

    try:
        sig_bytes = base64.b64decode(str(signature), validate=True)
        key_path = os.getenv("GENECODER_PLUGIN_PUBLIC_KEY")
        if not key_path:
            raise ValueError
        public_key = Path(key_path).read_bytes()
    except Exception as exc:
        raise ValueError("Invalid signature") from exc
    digest = plugin_security.compute_checksum(payload, signature=sig_bytes, public_key=public_key)
    expected = plugin_security.decode_checksum(str(checksum))
    if expected != digest:
        raise ValueError("Checksum mismatch")


def install_plugin_spec(
    spec: str,
    *,
    checksum: str,
    signature: str,
    allow_network: bool,
    installer: PluginInstaller,
) -> str:
    payload = _download_plugin_bytes(spec, allow_network=allow_network)
    _verify_payload(payload, checksum=checksum, signature=signature)

    tmp_path: str | None = None
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp_path = tmp.name
        tmp.write(payload)
        tmp.close()
        installer.install(tmp_path)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    return spec


def render_plugin_lock(descriptors: list[PluginDescriptor]) -> str:
    entries = sorted((d.as_lock_entry() for d in descriptors), key=lambda item: (item["name"], item["version"], item["source"]))
    return json.dumps({"plugins": entries}, indent=2, sort_keys=True)


def install_registry_plugins(
    url: str | os.PathLike[str] | None,
    *,
    offline: bool | None,
    allow_network: bool | None,
    yaml_module: ModuleType | None,
    installer: PluginInstaller | None = None,
) -> list[PluginDescriptor]:
    if isinstance(url, os.PathLike):
        url = os.fspath(url)
    if offline is None:
        offline = bool(os.getenv("GENECODER_OFFLINE"))
    if allow_network is None:
        allow_network = bool(os.getenv("GENECODER_ALLOW_NETWORK"))
    if url is None:
        url = os.getenv("GENECODER_PLUGIN_REGISTRY_URL")
    if not url:
        return []

    network_ok = allow_network and not offline
    raw = fetch_catalog(url, allow_network=network_ok)
    data = load_registry_mapping(raw, yaml_module)
    impl = installer or PipPluginInstaller()
    descriptors: list[PluginDescriptor] = []

    for entry in data.get("packages", []):
        if not isinstance(entry, Mapping):
            spec = str(entry)
            raise ValueError(f"Missing supply-chain metadata for plugin entry {spec}")

        spec = str(entry.get("spec") or entry.get("package") or entry.get("url") or "")
        checksum = cast(str | None, entry.get("checksum"))
        signature = cast(str | None, entry.get("signature"))
        version = str(entry.get("version") or "")
        name = str(entry.get("package") or spec)

        if not spec:
            continue
        validate_registry_license(entry, spec=spec)
        validate_spec(spec)
        if not checksum or not signature:
            raise ValueError("Signed metadata and checksum are required")

        descriptor = PluginDescriptor(name=name, kind="package", source=spec, version=version, checksum=checksum, signature=signature)
        descriptors.append(descriptor)
        try:
            install_plugin_spec(spec, checksum=checksum, signature=signature, allow_network=network_ok, installer=impl)
            descriptor.state = PluginLifecycleState.LOADED
        except Exception as exc:
            descriptor.state = PluginLifecycleState.FAILED
            descriptor.error = str(exc)
            raise
    return descriptors
