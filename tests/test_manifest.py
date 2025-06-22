import pytest

from genecoder.manifest import generate_manifest
from genecoder.cli import EncodingOptions


def test_generate_manifest_basic() -> None:
    opts = EncodingOptions(
        method="base4_direct",
        add_parity=False,
        k_value=7,
        parity_rule="PR",
        fec=None,
        gc_min=0.45,
        gc_max=0.55,
        max_homopolymer=3,
    )
    metrics = {"dna_length": 10}
    manifest = generate_manifest("file.txt", opts, metrics)
    assert manifest["file"] == "file.txt"
    assert manifest["encoding_parameters"]["method"] == "base4_direct"
    assert manifest["metrics"]["dna_length"] == 10


def test_generate_manifest_from_mapping() -> None:
    opts = {
        "method": "huffman",
        "add_parity": False,
        "k_value": 5,
        "parity_rule": "PR",
        "fec": None,
        "gc_min": 0.4,
        "gc_max": 0.6,
        "max_homopolymer": 3,
    }
    metrics = {"dna_length": 20, "num_records": 1}
    manifest = generate_manifest("data.bin", opts, metrics)
    assert manifest["file"] == "data.bin"
    assert manifest["encoding_parameters"]["method"] == "huffman"
    assert manifest["metrics"]["num_records"] == 1


def test_generate_manifest_invalid_type() -> None:
    with pytest.raises(ValueError, match="encoding_params must be a dataclass or mapping"):
        generate_manifest("bad.txt", ["not", "mapping"], {"dna_length": 1})


def test_generate_manifest_dataclass_type() -> None:
    with pytest.raises(ValueError, match="encoding_params must be a dataclass or mapping"):
        generate_manifest("bad.txt", EncodingOptions, {"dna_length": 1})
