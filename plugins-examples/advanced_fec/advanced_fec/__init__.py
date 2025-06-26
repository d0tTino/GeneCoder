from typing import Any, Callable

from genecoder.ldpc_codec import encode_data_ldpc, decode_data_ldpc


def register(
    register_fec: Callable[[str, Callable[[bytes], tuple[bytes, Any]], Callable[[bytes, Any], tuple[bytes, int]]], None]
) -> None:
    """Register a minimal LDPC FEC backend based on GeneCoder helpers."""
    register_fec("advanced_ldpc", encode_data_ldpc, decode_data_ldpc)
