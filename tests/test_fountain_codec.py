from genecoder.fountain_codec import encode_data_fountain, decode_data_fountain

def test_fountain_roundtrip():
    data = b"Fountain test data"
    encoded, info = encode_data_fountain(data, chunk_size=5)
    decoded, _ = decode_data_fountain(encoded, info)
    assert decoded == data


def test_fountain_empty_data():
    encoded, info = encode_data_fountain(b"", chunk_size=5)
    assert encoded == b""
    assert info["orig_len"] == 0
    decoded, _ = decode_data_fountain(encoded, info)
    assert decoded == b""


def test_fountain_erasure_recovery():
    data = b"robust fountain erasure test" * 3
    encoded, info = encode_data_fountain(data, chunk_size=4)
    droplet_size = info["chunk_size"] + 4
    droplets = [
        encoded[i : i + droplet_size] for i in range(0, len(encoded), droplet_size)
    ]
    # keep around 90% of droplets
    keep = int(len(droplets) * 0.9)
    subset = b"".join(droplets[:keep])
    decoded, _ = decode_data_fountain(subset, info)
    assert decoded == data
