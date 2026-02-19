from __future__ import annotations

from genecoder.plugin_api import Codec
from genecoder.plugin_runtime.descriptors import (
    PLUGIN_DESCRIPTOR_VERSION,
    PluginLifecycleState,
    RegistrationCapabilities,
    RuntimePluginDescriptor,
    ValidationContract,
)
from genecoder.plugin_runtime.registry import (
    CODEC_REGISTRY,
    REGISTRATION_STATES,
    register_plugin,
    transition_plugin_state,
)


class CodecV1(Codec):
    def encode(self, data: bytes, /, **kwargs: object) -> str:
        return data.decode("utf-8")[::-1]

    def decode(self, encoded: str, /, **kwargs: object) -> bytes:
        return encoded[::-1].encode("utf-8")


class CodecV2(CodecV1):
    def encode(self, data: bytes, /, **kwargs: object) -> str:
        return f"v2:{super().encode(data, **kwargs)}"

    def decode(self, encoded: str, /, **kwargs: object) -> bytes:
        return super().decode(encoded.replace("v2:", "", 1), **kwargs)


def _descriptor(name: str, impl: type[Codec]) -> RuntimePluginDescriptor:
    return RuntimePluginDescriptor(
        api_version=PLUGIN_DESCRIPTOR_VERSION,
        name=name,
        kind="codec",
        implementation=impl,
        capabilities=RegistrationCapabilities(deterministic=True),
        validation=ValidationContract(
            encode_input="bytes",
            encode_output="sequence",
            decode_input="sequence|batch",
            decode_output="bytes",
        ),
    )


def test_lifecycle_install_upgrade_disable_rollback_are_deterministic() -> None:
    CODEC_REGISTRY.clear()
    REGISTRATION_STATES.clear()

    register_plugin(_descriptor("demo", CodecV1))
    assert REGISTRATION_STATES["demo"] is PluginLifecycleState.LOADED
    assert CODEC_REGISTRY["demo"]["decode"]("cba") == b"abc"

    transition_plugin_state("demo", PluginLifecycleState.DISABLED)
    assert REGISTRATION_STATES["demo"] is PluginLifecycleState.DISABLED

    transition_plugin_state("demo", PluginLifecycleState.VALIDATED)
    register_plugin(_descriptor("demo", CodecV2))
    assert REGISTRATION_STATES["demo"] is PluginLifecycleState.LOADED
    assert CODEC_REGISTRY["demo"]["encode"](b"abc") == "v2:cba"

    transition_plugin_state("demo", PluginLifecycleState.ROLLED_BACK)
    transition_plugin_state("demo", PluginLifecycleState.VALIDATED)
    register_plugin(_descriptor("demo", CodecV1))

    assert REGISTRATION_STATES["demo"] is PluginLifecycleState.LOADED
    assert CODEC_REGISTRY["demo"]["encode"](b"abc") == "cba"
