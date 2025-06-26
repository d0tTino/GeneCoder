import os
import tempfile
from pathlib import Path

from genecoder.utils import get_temp_dir


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
