import json
import logging
import os
from pathlib import Path

import pytest

from genecoder.cli.encode import process_single_encode
from tests.test_cli_encode import _encode_args


def test_process_single_encode_gc_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    input_file = tmp_path / "gc.bin"
    input_file.write_bytes(b"\x00" * 8)
    output_file = tmp_path / "out_gc.fasta"
    os.environ["GENECODER_DISABLE_FIX"] = "1"
    args = _encode_args()
    args.gc_min = 0.4
    args.gc_max = 0.6
    args.max_homopolymer = 100
    caplog.set_level(logging.WARNING)
    process_single_encode(str(input_file), str(output_file), args)
    assert any("outside requested range" in rec.message for rec in caplog.records)
    assert not any("exceeds limit" in rec.message for rec in caplog.records)
    os.environ.pop("GENECODER_DISABLE_FIX", None)


def test_process_single_encode_homopolymer_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    input_file = tmp_path / "hp.bin"
    input_file.write_bytes(b"\x00" * 8)
    output_file = tmp_path / "out_hp.fasta"
    os.environ["GENECODER_DISABLE_FIX"] = "1"
    args = _encode_args()
    args.gc_min = 0.0
    args.gc_max = 1.0
    args.max_homopolymer = 4
    caplog.set_level(logging.WARNING)
    process_single_encode(str(input_file), str(output_file), args)
    assert any("exceeds limit" in rec.message for rec in caplog.records)
    assert not any("outside requested range" in rec.message for rec in caplog.records)
    os.environ.pop("GENECODER_DISABLE_FIX", None)


def test_default_constraint_warnings_and_manifest(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    input_file = tmp_path / "def.bin"
    input_file.write_bytes(b"\x00" * 8)
    output_file = tmp_path / "out_def.fasta"
    os.environ["GENECODER_DISABLE_FIX"] = "1"
    args = _encode_args()
    args.gc_min = 0.0
    args.gc_max = 1.0
    args.max_homopolymer = 100
    caplog.set_level(logging.WARNING)
    process_single_encode(str(input_file), str(output_file), args)
    os.environ.pop("GENECODER_DISABLE_FIX", None)
    assert any("recommended" in rec.message for rec in caplog.records)
    manifest_path = output_file.with_suffix(".manifest.json")
    data = json.loads(manifest_path.read_text())
    assert data["metrics"]["gc_exceeds_default"]
    assert data["metrics"]["homopolymer_exceeds_default"]


def test_suppress_default_constraint_warnings(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    input_file = tmp_path / "sup.bin"
    input_file.write_bytes(b"\x00" * 8)
    output_file = tmp_path / "out_sup.fasta"
    os.environ["GENECODER_DISABLE_FIX"] = "1"
    args = _encode_args()
    args.gc_min = 0.0
    args.gc_max = 1.0
    args.max_homopolymer = 100
    args.suppress_constraint_warnings = True
    caplog.set_level(logging.WARNING)
    process_single_encode(str(input_file), str(output_file), args)
    os.environ.pop("GENECODER_DISABLE_FIX", None)
    assert not any("recommended" in rec.message for rec in caplog.records)
    manifest_path = output_file.with_suffix(".manifest.json")
    data = json.loads(manifest_path.read_text())
    assert data["metrics"]["gc_exceeds_default"]
