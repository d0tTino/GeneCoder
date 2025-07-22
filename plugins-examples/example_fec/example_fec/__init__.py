from typing import Callable, Mapping, Any
from genecoder.api import FEC


class ExampleFEC(FEC):  # type: ignore[misc]
    def encode(self, data: bytes) -> tuple[bytes, Mapping[str, Any]]:
        return data, {}

    def decode(self, encoded: bytes, info: Mapping[str, Any]) -> tuple[bytes, int]:
        return encoded, 0


def register(register_fec: Callable[[str, type[FEC]], None]) -> None:
    """Register a simple example FEC."""

    register_fec("example", ExampleFEC)
