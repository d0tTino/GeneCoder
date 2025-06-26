import tempfile
from pathlib import Path

from genecoder.utils import get_temp_dir


def test_get_temp_dir_env_override(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("GENECODER_TMP", tmpdir)
        assert get_temp_dir() == Path(tmpdir)
