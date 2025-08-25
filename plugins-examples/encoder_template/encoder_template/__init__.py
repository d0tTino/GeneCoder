from typing import Callable

from genecoder.api import Codec


class TemplateEncoder(Codec):  # type: ignore[misc]
    """Skeleton encoder plugin."""

    def encode(self, data: bytes, /, **kwargs: object) -> str:
        """Convert ``data`` into a DNA string."""
        raise NotImplementedError

    def decode(self, text: str, /, **kwargs: object) -> bytes:
        """Reconstruct the original bytes from ``text``."""
        raise NotImplementedError


def register(register_codec: Callable[[str, type[Codec]], None]) -> None:
    """Register the encoder with GeneCoder."""
    register_codec("template", TemplateEncoder)
