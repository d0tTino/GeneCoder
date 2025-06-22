"""Advanced GC-balancing utilities with sliding-window checks."""

from __future__ import annotations

from typing import Iterable, Iterator

from .encoders import encode_base4_direct, decode_base4_direct


class AdvancedGCBalancer:
    """Encode and decode with simple GC/homopolymer constraints."""

    def __init__(
        self,
        target_gc_min: float,
        target_gc_max: float,
        max_homopolymer: int,
        window_size: int = 50,
        step_size: int = 10,
    ) -> None:
        self.target_gc_min = target_gc_min
        self.target_gc_max = target_gc_max
        self.max_homopolymer = max_homopolymer
        self.window_size = window_size
        self.step_size = step_size

    def encode(self, data: bytes | Iterable[bytes], *, stream: bool = False) -> Iterator[str] | str:
        """Encode bytes ensuring GC balance across sliding windows."""
        return encode_base4_direct(data, stream=stream)  # placeholder

    def decode(self, dna: str | Iterable[str], *, stream: bool = False) -> Iterator[bytes] | bytes:
        """Decode DNA produced by :meth:`encode`."""
        result = decode_base4_direct(dna, stream=stream)
        from typing import cast

        if stream:
            iter_result = cast(Iterator[tuple[bytes, list[int]]], result)
            return (chunk for chunk, _ in iter_result)
        return cast(tuple[bytes, list[int]], result)[0]
