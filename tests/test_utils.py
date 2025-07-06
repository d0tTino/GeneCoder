import os
import tempfile
from pathlib import Path

from genecoder.utils import get_temp_dir, bit_error_rate


def test_get_temp_dir_env_override(monkeypatch):
    with tempfile.TemporaryDirectory(dir=get_temp_dir()) as tmpdir:
        monkeypatch.setenv("GENECODER_TMP", tmpdir)
        assert get_temp_dir() == Path(tmpdir)


def test_tempdir_respects_env(monkeypatch):
    with tempfile.TemporaryDirectory(dir=get_temp_dir()) as base:
        monkeypatch.setenv("GENECODER_TMP", base)
        with tempfile.TemporaryDirectory(dir=get_temp_dir()) as sub:
            assert Path(sub).parent == Path(base)


def test_mkdtemp_respects_env(monkeypatch):
    with tempfile.TemporaryDirectory(dir=get_temp_dir()) as base:
        monkeypatch.setenv("GENECODER_TMP", base)
        path = tempfile.mkdtemp(dir=get_temp_dir())
        try:
            assert Path(path).parent == Path(base)
        finally:
            os.rmdir(path)


def test_bit_error_rate_identical() -> None:
    assert bit_error_rate(b"abc", b"abc") == 0.0


def test_bit_error_rate_basic() -> None:
    original = b"\x00"
    recovered = b"\x01"
    assert bit_error_rate(original, recovered) == 1 / 8
