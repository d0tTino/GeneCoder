import numpy as np
import pytest

from genecoder.ldpc_codec import (
    _require_pyldpc,
    encode_data_ldpc,
    decode_data_ldpc,
)
from genecoder.fountain_codec import encode_data_fountain, decode_data_fountain


def test_ldpc_missing_dependency(monkeypatch):
    monkeypatch.setattr('genecoder.ldpc_codec._HAS_PYLDPC', False)
    with pytest.raises(ImportError):
        _require_pyldpc()


def test_ldpc_encode_decode_roundtrip(monkeypatch):
    monkeypatch.setattr('genecoder.ldpc_codec._HAS_PYLDPC', True)
    monkeypatch.setattr('genecoder.ldpc_codec.np', __import__('numpy'))
    monkeypatch.setattr('genecoder.ldpc_codec.make_ldpc', lambda n_bits, **k: (np.eye(n_bits, dtype=np.uint8), np.eye(n_bits, dtype=np.uint8)))
    monkeypatch.setattr('genecoder.ldpc_codec.utils', __import__('types').SimpleNamespace(binaryproduct=lambda g,m:m))
    monkeypatch.setattr('genecoder.ldpc_codec.decode', lambda H,bits,snr=2: bits)
    data = b'abcd'
    encoded, info = encode_data_ldpc(data)
    decoded, corrections = decode_data_ldpc(encoded, info)
    assert decoded.startswith(data)
    assert corrections == 0


def test_fountain_parity(monkeypatch):
    monkeypatch.setattr('genecoder.fountain_codec._HAS_PYFINITE', True)
    monkeypatch.setattr('genecoder.fountain_codec.ffield', __import__('types').SimpleNamespace(FField=lambda _: __import__('types').SimpleNamespace(Add=lambda a,b:a ^ b)))
    data = bytes([1, 2, 3, 4])
    encoded, info = encode_data_fountain(data, chunk_size=4)
    parity = encoded[-4:]
    decoded, _ = decode_data_fountain(encoded, info)
    assert decoded == data
    assert any(parity) and len(parity) == 4
