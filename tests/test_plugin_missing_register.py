import sys
from pathlib import Path
from types import ModuleType
import importlib
import pytest

from genecoder import plugins


def _clear_registries() -> None:
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()


def test_local_plugin_without_register(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pkg = tmp_path / "plugins"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "dummy.py").write_text("x = 1\n")
    monkeypatch.syspath_prepend(tmp_path)
    monkeypatch.chdir(tmp_path)
    # Ensure our package is imported instead of any existing one
    sys.modules.pop("plugins", None)
    _clear_registries()
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])
    plugins.load_plugins()
    assert "dummy" not in plugins.CODEC_REGISTRY
    assert "dummy" not in plugins.FEC_REGISTRY
    assert "dummy" not in plugins.SIMULATOR_REGISTRY
    # built-in FEC should still be loaded
    assert "reed_solomon" in plugins.FEC_REGISTRY
    sys.modules.pop("plugins", None)
    plugins.load_plugins()


def test_entry_point_without_register(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_mod = ModuleType("dummy_ep")

    class DummyEP:
        def load(self) -> ModuleType:
            return dummy_mod

    def fake_entry_points(*, group: str | None = None) -> list[object]:
        if group == "genecoder.plugins":
            return [DummyEP()]
        return []

    _clear_registries()
    monkeypatch.setattr(plugins, "entry_points", fake_entry_points)
    # prevent scanning local plugins
    dummy_pkg = ModuleType("plugins")
    dummy_pkg.__path__ = []
    monkeypatch.setitem(sys.modules, "plugins", dummy_pkg)
    plugins.load_plugins()
    # Restore original environment and reload built-in plugins
    monkeypatch.setattr(plugins, "entry_points", importlib.metadata.entry_points)
    sys.modules.pop("plugins", None)
    plugins.load_plugins()
    assert "dummy_ep" not in plugins.CODEC_REGISTRY
    assert "dummy_ep" not in plugins.FEC_REGISTRY
    assert "dummy_ep" not in plugins.SIMULATOR_REGISTRY

