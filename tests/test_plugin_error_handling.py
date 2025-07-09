import logging
from importlib.metadata import EntryPoint
import pytest

import genecoder.plugin_manager as plugins


def test_load_plugins_reports_failures(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    def fake_entry_points(*, group: str | None = None):
        if group == "genecoder.plugins":
            return [EntryPoint(name="bad", value="missing_mod", group=group)]
        return []

    monkeypatch.setattr(plugins, "entry_points", fake_entry_points)

    original_import = plugins.importlib.import_module

    def fake_import(name: str, package: str | None = None):
        if name == "missing_mod":
            raise ImportError("boom")
        return original_import(name, package)

    monkeypatch.setattr(plugins.importlib, "import_module", fake_import)

    with caplog.at_level(logging.WARNING):
        plugins.load_plugins()

    assert "missing_mod" in caplog.text
    # aggregated warning appears once
    assert caplog.text.count("Failed to import plugins") == 1
