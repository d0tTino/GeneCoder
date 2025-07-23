"""Advanced GC-balancing utilities with sliding-window checks."""

from __future__ import annotations

from typing import Iterable, cast

from .gc_constrained_encoder import calculate_gc_content
from .utils import get_max_homopolymer_length

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

    def _windows(self, sequence: str) -> Iterable[str]:
        """Yield sliding windows from ``sequence``."""
        if len(sequence) < self.window_size:
            yield sequence
        else:
            for i in range(0, len(sequence) - self.window_size + 1, self.step_size):
                yield sequence[i : i + self.window_size]

    def _check_constraints(self, sequence: str) -> bool:
        """Return ``True`` if all windows satisfy GC and homopolymer limits."""
        for window in self._windows(sequence):
            gc = calculate_gc_content(window)
            if gc < self.target_gc_min or gc > self.target_gc_max:
                return False
            if get_max_homopolymer_length(window) > self.max_homopolymer:
                return False
        return True

    def _window_ok(self, window: str) -> bool:
        """Return ``True`` if ``window`` meets GC and homopolymer limits."""
        gc = calculate_gc_content(window)
        if gc < self.target_gc_min or gc > self.target_gc_max:
            return False
        if get_max_homopolymer_length(window) > self.max_homopolymer:
            return False
        return True

    def encode(
        self, data: bytes | Iterable[bytes], *, stream: bool = False
    ) -> str | Iterable[str]:
        """Encode bytes ensuring GC balance across sliding windows."""
        if stream:
            iterable = [data] if isinstance(data, (bytes, bytearray)) else data

            def gen() -> Iterable[str]:
                dna_so_far = ""
                next_start = 0
                for dna_chunk in cast(
                    Iterable[str], encode_base4_direct(iterable, stream=True)
                ):
                    dna_so_far += dna_chunk
                    while next_start <= len(dna_so_far) - self.window_size:
                        window = dna_so_far[next_start : next_start + self.window_size]
                        if not self._window_ok(window):
                            raise ValueError(
                                "Encoded sequence violates GC content or homopolymer constraints"
                            )
                        next_start += self.step_size
                    yield dna_chunk
                if not self._check_constraints(dna_so_far):
                    raise ValueError(
                        "Encoded sequence violates GC content or homopolymer constraints"
                    )

            return gen()
        if not isinstance(data, (bytes, bytearray)):
            data = b"".join(data)
        dna = cast(str, encode_base4_direct(data, stream=False))
        if not self._check_constraints(dna):
            raise ValueError("Encoded sequence violates GC content or homopolymer constraints")
        return dna

    def decode(
        self, dna: str | Iterable[str], *, stream: bool = False
    ) -> bytes | Iterable[bytes]:
        """Decode DNA produced by :meth:`encode`."""
        if stream:
            iterable = [dna] if isinstance(dna, str) else dna

            def gen() -> Iterable[bytes]:
                dna_so_far = ""
                next_start = 0
                for chunk in iterable:
                    dna_so_far += chunk
                    while next_start <= len(dna_so_far) - self.window_size:
                        window = dna_so_far[next_start : next_start + self.window_size]
                        if not self._window_ok(window):
                            raise ValueError(
                                "DNA sequence violates GC content or homopolymer constraints"
                            )
                        next_start += self.step_size
                    decoded_tuple = cast(
                        tuple[bytes, list[int]],
                        decode_base4_direct(chunk, stream=False),
                    )
                    yield decoded_tuple[0]
                if not self._check_constraints(dna_so_far):
                    raise ValueError(
                        "DNA sequence violates GC content or homopolymer constraints"
                    )

            return gen()
        if not isinstance(dna, str):
            dna = "".join(dna)
        if not self._check_constraints(dna):
            raise ValueError("DNA sequence violates GC content or homopolymer constraints")
        decoded_tuple = cast(
            tuple[bytes, list[int]], decode_base4_direct(dna, stream=False)
        )
        return decoded_tuple[0]
