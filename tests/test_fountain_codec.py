import random

import pytest

pytest.importorskip("pyfinite")

from genecoder.fountain_codec import (
    _robust_soliton_cdf,
    _sample_degree,
    decode_data_fountain,
    encode_data_fountain,
)

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


def test_fountain_degree_distribution_params():
    data = b"distribution" * 20
    encoded_default, info_default = encode_data_fountain(
        data, chunk_size=3, redundancy=1.0, seed=0
    )
    encoded_custom, info_custom = encode_data_fountain(
        data, chunk_size=3, redundancy=1.0, seed=0, c=0.2, delta=0.3
    )

    def degree_hist(encoded, info):
        k = info["k"]
        chunk_size = info["chunk_size"]
        droplet_size = chunk_size + 4
        cdf = _robust_soliton_cdf(k, c=info["c"], delta=info["delta"])
        hist: dict[int, int] = {}
        for i in range(0, len(encoded), droplet_size):
            seed = int.from_bytes(encoded[i : i + 4], "big")
            rnd = random.Random(seed)
            degree = _sample_degree(cdf, rnd)
            hist[degree] = hist.get(degree, 0) + 1
        return hist

    hist_default = degree_hist(encoded_default, info_default)
    hist_custom = degree_hist(encoded_custom, info_custom)
    assert hist_default != hist_custom
