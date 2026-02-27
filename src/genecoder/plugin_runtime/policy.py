from __future__ import annotations

import inspect
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from genecoder import plugin_security

from .descriptors import (
    PLUGIN_DESCRIPTOR_VERSION,
    PluginLifecycleState,
    RuntimePluginDescriptor,
)

logger = logging.getLogger(__name__)

VALID_INTERFACES = {"codec", "FEC", "fec", "simulator", "visualizer"}
ALLOWED_LICENSES = {
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "MIT",
}

SAFE_PKG_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
SAFE_URL_RE = re.compile(r"^(?:https?|file)://[A-Za-z0-9._~:/?#@!$&'()*+,;=%-]+$")


def validate_spec(spec: str) -> None:
    if not spec or re.search(r"[\s;&|`$<>]", spec):
        raise ValueError("Unsafe plugin spec")
    if SAFE_PKG_RE.fullmatch(spec) or SAFE_URL_RE.fullmatch(spec):
        return
    raise ValueError("Unsafe plugin spec")


def validate_registry_license(entry: Mapping[str, Any], *, spec: str) -> str:
    license_value = entry.get("license")
    if not isinstance(license_value, str) or not license_value.strip():
        message = f"Missing license for plugin entry {spec}"
        logger.error(message)
        raise ValueError(message)
    normalized = license_value.strip()
    if normalized not in ALLOWED_LICENSES:
        allowed = ", ".join(sorted(ALLOWED_LICENSES))
        message = (
            f"Disallowed license {normalized!r} for plugin entry {spec}. "
            f"Allowed licenses: {allowed}"
        )
        logger.error(message)
        raise ValueError(message)
    return normalized


def validate_plugin_metadata(meta: object) -> dict[str, Any]:
    if not isinstance(meta, dict):
        raise TypeError("PLUGIN_METADATA must be a dict")
    name = meta.get("name")
    version = meta.get("version")
    interfaces = meta.get("interfaces")
    license_value = meta.get("license")
    if not isinstance(name, str) or not name:
        raise ValueError("PLUGIN_METADATA.name is required and must be a non-empty string")
    if not isinstance(version, str) or not version:
        raise ValueError("PLUGIN_METADATA.version is required and must be a non-empty string")
    if not isinstance(interfaces, (list, tuple)) or not interfaces:
        raise ValueError("PLUGIN_METADATA.interfaces is required and must be a non-empty list")
    if any(i not in VALID_INTERFACES for i in interfaces):
        raise ValueError("PLUGIN_METADATA.interfaces contains an unknown interface")
    if not isinstance(license_value, str) or not license_value.strip():
        raise ValueError(
            "PLUGIN_METADATA.license is required and must be a non-empty SPDX identifier"
        )
    normalized = license_value.strip()
    if normalized not in ALLOWED_LICENSES:
        allowed = ", ".join(sorted(ALLOWED_LICENSES))
        raise ValueError(
            f"PLUGIN_METADATA.license {normalized!r} is not allowed. Allowed licenses: {allowed}"
        )
    return {
        "name": name,
        "version": version,
        "interfaces": list(interfaces),
        "license": normalized,
    }


def validate_runtime_descriptor(descriptor: RuntimePluginDescriptor) -> RuntimePluginDescriptor:
    if descriptor.api_version != PLUGIN_DESCRIPTOR_VERSION:
        raise ValueError(
            f"Unsupported plugin registration API version {descriptor.api_version!r}; "
            f"expected {PLUGIN_DESCRIPTOR_VERSION!r}"
        )
    if descriptor.kind not in VALID_INTERFACES:
        raise ValueError(f"Unsupported plugin kind {descriptor.kind!r}")
    kind = "fec" if descriptor.kind == "FEC" else descriptor.kind
    capability_interface = getattr(descriptor.capabilities, "interface", "")
    if capability_interface and capability_interface != kind:
        raise ValueError(
            f"Capability interface {capability_interface!r} does not match descriptor kind {kind!r}"
        )
    interface_version = getattr(descriptor.capabilities, "interface_version", "")
    if interface_version and interface_version != PLUGIN_DESCRIPTOR_VERSION and not interface_version.startswith("1."):
        raise ValueError(f"Unsupported interface version {interface_version!r}")
    if not descriptor.name or not descriptor.name.strip():
        raise ValueError("Plugin descriptor name must be a non-empty string")
    return descriptor


ALLOWED_LIFECYCLE_TRANSITIONS: dict[PluginLifecycleState, tuple[PluginLifecycleState, ...]] = {
    PluginLifecycleState.DISCOVERED: (PluginLifecycleState.VALIDATED, PluginLifecycleState.DISABLED, PluginLifecycleState.FAILED),
    PluginLifecycleState.VALIDATED: (PluginLifecycleState.LOADED, PluginLifecycleState.DISABLED, PluginLifecycleState.FAILED),
    PluginLifecycleState.LOADED: (PluginLifecycleState.VALIDATED, PluginLifecycleState.DISABLED, PluginLifecycleState.ROLLED_BACK, PluginLifecycleState.FAILED),
    PluginLifecycleState.DISABLED: (PluginLifecycleState.VALIDATED, PluginLifecycleState.ROLLED_BACK, PluginLifecycleState.FAILED),
    PluginLifecycleState.ROLLED_BACK: (PluginLifecycleState.VALIDATED, PluginLifecycleState.DISABLED, PluginLifecycleState.FAILED),
    PluginLifecycleState.FAILED: (PluginLifecycleState.DISCOVERED,),
}


def enforce_lifecycle_transition(
    current: PluginLifecycleState,
    nxt: PluginLifecycleState,
) -> PluginLifecycleState:
    allowed = ALLOWED_LIFECYCLE_TRANSITIONS.get(current, ())
    if nxt not in allowed:
        raise ValueError(f"Invalid plugin lifecycle transition: {current.value} -> {nxt.value}")
    return nxt


def check_signature(impl: Callable[..., Any], base: Callable[..., Any], *, kind: str, method: str) -> None:
    params = list(inspect.signature(base).parameters.values())
    if params and params[0].name == "self":
        params = params[1:]
    impl_sig = inspect.signature(impl)
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params):
        if not any(p.kind == inspect.Parameter.VAR_KEYWORD for p in impl_sig.parameters.values()):
            raise TypeError(f"{kind} {method} must accept **kwargs")
    args = [object() for p in params if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    kwargs = {p.name: object() for p in params if p.kind == inspect.Parameter.KEYWORD_ONLY}
    try:
        impl_sig.bind(*args, **kwargs)
    except TypeError as exc:
        raise TypeError(f"{kind} {method} has incompatible signature: {exc}") from exc


def coerce_plugin(obj: object, expected: type[object], methods: Iterable[str], kind: str) -> object:
    if isinstance(obj, type):
        if not issubclass(obj, expected):
            raise TypeError(f"{kind} must subclass {expected.__name__}")
        instance: object = obj()
    else:
        if not isinstance(obj, expected):
            raise TypeError(f"{kind} must subclass {expected.__name__}")
        instance = obj
    for method in methods:
        method_impl = getattr(instance, method, None)
        if not callable(method_impl):
            raise TypeError(f"{kind} missing required method {method}")
        check_signature(method_impl, getattr(expected, method), kind=kind, method=method)
    return instance


def decode_and_verify_checksum(
    payload: bytes,
    *,
    checksum: str | None = None,
    signature_b64: str | None = None,
    public_key_env_var: str = "GENECODER_PLUGIN_PUBLIC_KEY",
) -> bytes:
    signature = None
    public_key = None
    if signature_b64:
        import base64

        try:
            signature = base64.b64decode(str(signature_b64), validate=True)
            public_key = Path(os.environ[public_key_env_var]).read_bytes()
        except Exception as exc:
            raise ValueError("Invalid signature") from exc
    digest = plugin_security.compute_checksum(payload, signature=signature, public_key=public_key)
    if checksum:
        expected = plugin_security.decode_checksum(str(checksum))
        if digest != expected:
            raise ValueError("Checksum mismatch")
    return digest
