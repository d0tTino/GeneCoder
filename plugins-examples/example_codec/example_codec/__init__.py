from typing import Callable


def register(
    register_codec: Callable[[str, Callable[[bytes], str], Callable[[str], bytes]], None]
) -> None:
    """Register a simple example codec."""

    def encode(data: bytes) -> str:
        return data.hex()

    def decode(text: str) -> bytes:
        return bytes.fromhex(text)

    register_codec("example", encode, decode)
