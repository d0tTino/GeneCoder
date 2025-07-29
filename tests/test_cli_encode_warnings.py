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
