"""Sample plugin providing a simple reverse codec."""

from typing import Callable


def register(register_codec: Callable[[str, Callable, Callable], None]) -> None:
    """Register the reverse codec."""

    def encode_reverse(data: bytes) -> str:
        return data[::-1].decode("utf-8")

    def decode_reverse(text: str) -> bytes:
        return text[::-1].encode("utf-8")

    register_codec("reverse", encode_reverse, decode_reverse)
