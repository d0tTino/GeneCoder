
import pytest
from dataclasses import dataclass

from genecoder.manifest import generate_manifest
from genecoder.core import run_pipeline
from genecoder.api import Codec
from genecoder.plugin_manager import CODEC_REGISTRY, init_plugins
import json
from genecoder.cli import EncodingOptions
from pathlib import Path
import os


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
    file_path = Path("dir/sub") / "file.txt"
    manifest = generate_manifest(file_path, opts, metrics)
    assert manifest["file"] == os.path.basename(file_path.as_posix())
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
    file_path = Path("dir") / "data.bin"
    manifest = generate_manifest(file_path, opts, metrics)
    assert manifest["file"] == os.path.basename(file_path.as_posix())
    assert manifest["encoding_parameters"]["method"] == "huffman"
    assert manifest["metrics"]["num_records"] == 1


def test_generate_manifest_invalid_type() -> None:
    with pytest.raises(ValueError, match="encoding_params must be a dataclass or mapping"):
        generate_manifest("bad.txt", ["not", "mapping"], {"dna_length": 1})


def test_generate_manifest_dataclass_type() -> None:
    with pytest.raises(ValueError, match="encoding_params must be a dataclass or mapping"):
        generate_manifest("bad.txt", EncodingOptions, {"dna_length": 1})


def test_generate_manifest_missing_required_key_mapping() -> None:
    opts = {"add_parity": False}
    with pytest.raises(ValueError, match="Missing required encoding parameter\(s\): method"):
        generate_manifest("bad.txt", opts, {"dna_length": 1})


def test_generate_manifest_missing_required_key_dataclass() -> None:
    @dataclass
    class NoMethod:
        add_parity: bool = False

    with pytest.raises(ValueError, match="Missing required encoding parameter\(s\): method"):
        generate_manifest("bad.txt", NoMethod(), {"dna_length": 1})


class _Base4Codec(Codec):
    def encode(self, data: bytes) -> str:  # type: ignore[override]
        from genecoder.encoders import encode_base4_direct
        return encode_base4_direct(data)  # type: ignore[return-value]

    def decode(self, encoded: str) -> bytes:  # type: ignore[override]
        from genecoder.encoders import decode_base4_direct
        return decode_base4_direct(encoded)[0]


def test_pipeline_manifest_metrics(tmp_path: Path) -> None:
    init_plugins()
    CODEC_REGISTRY["base4"] = {"encode": _Base4Codec().encode, "decode": _Base4Codec().decode}
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(b"ACGTACGT")

    result, metrics = run_pipeline("base4", None, "none", str(inp), str(outp))
    assert result == b"ACGTACGT"

    manifest = generate_manifest(inp.name, {"method": "base4"}, metrics)
    manifest_path = tmp_path / "m.json"
    manifest_path.write_text(json.dumps(manifest))

    from genecoder import dashboard

    loaded = dashboard._load_metrics(str(manifest_path))
    assert loaded["gc_content"] == metrics["gc_content"]
    assert loaded["max_homopolymer"] == metrics["max_homopolymer"]

