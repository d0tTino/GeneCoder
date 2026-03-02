from typing import Callable
from genecoder.sdk.plugins import Codec


class ExampleCodec(Codec):  # type: ignore[misc]
    def encode(self, data: bytes, /, **kwargs: object) -> str:
        return data.hex()

    def decode(self, text: str, /, **kwargs: object) -> bytes:
        return bytes.fromhex(text)


def register(register_codec: Callable[[str, type[Codec]], None]) -> None:
    """Register a simple example codec."""

    register_codec("example", ExampleCodec)
