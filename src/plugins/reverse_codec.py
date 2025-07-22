"""Sample plugin providing a simple reverse codec."""

from typing import Callable

from genecoder.codecs import BaseCodec


class ReverseCodec(BaseCodec):  # type: ignore[misc]
    """Simple byte-reversing codec."""

    def encode(self, data: bytes, /) -> str:
        return data[::-1].decode("utf-8")

    def decode(self, encoded: str, /) -> bytes:
        return encoded[::-1].encode("utf-8")


def register(register_codec: Callable[[str, type[BaseCodec]], None]) -> None:
    """Register the reverse codec."""

    register_codec("reverse", ReverseCodec)

