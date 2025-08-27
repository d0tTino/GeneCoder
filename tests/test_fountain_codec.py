import random

import pytest

pytest.importorskip("pyfinite")
pytest.importorskip("reedsolo")

from genecoder.fountain_codec import (
    _robust_soliton_cdf,
    _sample_degree,
    decode_data_fountain,
    encode_data_fountain,
)
from genecoder.reed_solomon_codec import encode_data_rs, decode_data_rs

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


def test_fountain_roundtrip_explicit_droplets():
    data = b"explicit droplet count"
    encoded, info = encode_data_fountain(
        data, chunk_size=3, droplet_count=20, seed=1
    )
    decoded, _ = decode_data_fountain(encoded, info)
    assert decoded == data


def test_fountain_droplet_loss_with_explicit_count():
    data = b"loss scenario" * 4
    encoded, info = encode_data_fountain(
        data, chunk_size=4, droplet_count=40, seed=2
    )
    droplet_size = info["chunk_size"] + 4
    droplets = [
        encoded[i : i + droplet_size] for i in range(0, len(encoded), droplet_size)
    ]
    subset = b"".join(droplets[:-10])
    decoded, _ = decode_data_fountain(subset, info)
    assert decoded == data


def test_fountain_with_reed_solomon_outer_code():
    data = b"rs outer integration"
    rs_encoded, nsym, sym_size, prim = encode_data_rs(data, nsym=4)
    encoded, info = encode_data_fountain(
        rs_encoded, chunk_size=5, droplet_count=30, seed=3
    )
    droplet_size = info["chunk_size"] + 4
    droplets = [
        encoded[i : i + droplet_size] for i in range(0, len(encoded), droplet_size)
    ]
    subset = b"".join(droplets[:-5])
    fountain_decoded, _ = decode_data_fountain(subset, info)
    rs_decoded, _ = decode_data_rs(
        fountain_decoded, nsym, symbol_size=sym_size, primitive=prim
    )
    assert rs_decoded == data


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


def test_fountain_decode_degree_distribution_override():
    data = b"distribution" * 20
    encoded, info = encode_data_fountain(
        data, chunk_size=3, redundancy=1.0, seed=0
    )

    def degree_hist(c: float, delta: float) -> dict[int, int]:
        k = info["k"]
        chunk_size = info["chunk_size"]
        droplet_size = chunk_size + 4
        cdf = _robust_soliton_cdf(k, c=c, delta=delta)
        hist: dict[int, int] = {}
        for i in range(0, len(encoded), droplet_size):
            seed = int.from_bytes(encoded[i : i + 4], "big")
            rnd = random.Random(seed)
            degree = _sample_degree(cdf, rnd)
            hist[degree] = hist.get(degree, 0) + 1
        return hist

    hist_default = degree_hist(info["c"], info["delta"])
    hist_override = degree_hist(info["c"] * 2, info["delta"] / 2)
    assert hist_default != hist_override
