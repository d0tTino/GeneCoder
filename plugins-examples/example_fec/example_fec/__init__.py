from typing import Any, Callable


def register(
    register_fec: Callable[[str, Callable[[bytes], bytes], Callable[[bytes, Any], bytes]], None]
) -> None:
    """Register a simple example FEC."""

    def encode(data: bytes) -> bytes:
        return data

    def decode(encoded: bytes, info: Any | None = None) -> bytes:
        return encoded

    register_fec("example", encode, decode)
