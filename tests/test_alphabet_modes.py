from genecoder.encoders import encode_base4_direct, decode_base4_direct
from genecoder.utils import get_alphabet_maps


def _roundtrip(alphabet: str) -> None:
    encode_map, decode_map = get_alphabet_maps(alphabet)
    data = b"Hello"
    dna = encode_base4_direct(data, encode_map=encode_map)
    decoded, errors = decode_base4_direct(dna, decode_map=decode_map)
    assert decoded == data
    assert errors == []


def test_base4_roundtrip() -> None:
    _roundtrip("base4")


def test_base5_roundtrip() -> None:
    _roundtrip("base5")


def test_base6_roundtrip() -> None:
    _roundtrip("base6")
