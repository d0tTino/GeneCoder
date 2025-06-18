import sys
from pathlib import Path
import pytest

from genecoder import plugins


def test_plugins_py_module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mod = tmp_path / "plugins.py"
    mod.write_text("x = 1\n")
    monkeypatch.syspath_prepend(tmp_path)
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("plugins", None)
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])
    plugins.load_plugins()
    assert "reverse" in plugins.CODEC_REGISTRY
    assert "reed_solomon" in plugins.FEC_REGISTRY
    assert "ldpc" in plugins.FEC_REGISTRY
    assert "fountain" in plugins.FEC_REGISTRY
