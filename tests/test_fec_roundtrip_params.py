import os

import pytest

from genecoder.reed_solomon_codec import (
    encode_data_rs,
    decode_data_rs,
    _HAS_REEDSOLO,
)
from genecoder.fountain_codec import encode_data_fountain, decode_data_fountain


@pytest.mark.skipif(not _HAS_REEDSOLO, reason="reedsolo not installed")
@pytest.mark.parametrize("nsym,length", [(5, 16), (12, 32)])
def test_reed_solomon_roundtrip_params(nsym, length):
    data = os.urandom(length)
    encoded, used_nsym = encode_data_rs(data, nsym=nsym)
    decoded, corrected = decode_data_rs(encoded, used_nsym)
    assert decoded == data
    assert corrected == 0


@pytest.mark.parametrize("chunk_size,length", [(3, 10), (8, 25)])
def test_fountain_roundtrip_params(chunk_size, length):
    data = os.urandom(length)
    batch, info = encode_data_fountain(data, chunk_size=chunk_size)
    assert info["chunk_size"] == chunk_size
    decoded, _ = decode_data_fountain(batch, info)
    assert decoded == data
