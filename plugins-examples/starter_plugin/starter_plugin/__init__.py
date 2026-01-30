"""Starter plugin showing the minimal codec hook surface.

The :data:`PLUGIN_METADATA` dictionary is used to populate the plugin catalog
that ``genecli plugin list`` displays. Adjust the fields to match your plugin's
name, version and supported interfaces. For simulators, change the interface to
``"simulator"`` and wire up the registration call accordingly.
"""

from typing import Callable

from genecoder.api import Codec

# Metadata that will show up in the plugin catalog; keep the interfaces list
# aligned with the entry point group(s) used below.
PLUGIN_METADATA = {
    "name": "starter-template",
    "version": "0.1.0",
    "interfaces": ["codec"],
    "license": "MIT",
}


class StarterTemplateCodec(Codec):  # type: ignore[misc]
    """A minimal codec that reverses bytes to create a string payload.

    Replace this class with your own codec implementation. For a simulator
    template, import :class:`genecoder.api.Simulator` instead of
    :class:`genecoder.api.Codec` and update the :func:`register` hook to call
    ``register_simulator``.
    """

    def encode(self, data: bytes, /, **kwargs: object) -> str:
        # Provide any custom encode logic here; keep kwargs for forward-compat.
        return data[::-1].decode("utf-8")

    def decode(self, text: str, /, **kwargs: object) -> bytes:
        # Mirror the encode path so round trips succeed in quick demos/tests.
        return text[::-1].encode("utf-8")


def register(register_codec: Callable[[str, type[Codec]], None]) -> None:
    """Entry point that GeneCoder calls to register the plugin.

    The ``register_codec`` callable is provided by the plugin manager. Swap this
    out for ``register_simulator`` in the function signature if you build a
    simulator plugin.
    """

    register_codec("starter_template", StarterTemplateCodec)
