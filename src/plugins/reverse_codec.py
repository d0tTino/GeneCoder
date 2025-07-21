"""Sample plugin providing a simple reverse codec."""

from typing import Callable

from genecoder.codecs import BaseCodec


class ReverseCodec(BaseCodec):
    """Simple byte-reversing codec."""

    def encode(self, data: bytes, /) -> str:  # type: ignore[override]
        return data[::-1].decode("utf-8")

    def decode(self, encoded: str, /) -> bytes:  # type: ignore[override]
        return encoded[::-1].encode("utf-8")


def register(
    register_codec: Callable[[str, Callable[..., object], Callable[..., object]], None]
) -> None:
    """Register the reverse codec."""

    register_codec("reverse", ReverseCodec)

