from typing import Callable


def register(register_codec: Callable[[str, Callable[[bytes], str], Callable[[str], bytes]], None]) -> None:
    """Register a simple package plugin."""

    def encode(data: bytes) -> str:
        return data.decode("utf-8")[::-1]

    def decode(text: str) -> bytes:
        return text[::-1].encode("utf-8")

    register_codec("package_example", encode, decode)
