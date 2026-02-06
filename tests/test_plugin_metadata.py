import logging
import sys
import types

import pytest

import genecoder.plugin_manager as plugins


def test_entry_point_metadata_missing_license(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    module = types.ModuleType("ep_no_license")
    module.PLUGIN_METADATA = {
        "name": "ep-no-license",
        "version": "1.0",
        "interfaces": ["codec"],
    }
    monkeypatch.setitem(sys.modules, "ep_no_license", module)

    class EP:
        name = "ep_no_license"
        group = "genecoder.plugins"
        value = "ep_no_license"

        def load(self) -> types.ModuleType:
            return module

    monkeypatch.setattr(
        plugins,
        "entry_points",
        lambda group=None: [EP()] if group in (None, "genecoder.plugins") else [],
    )
    plugins.PLUGIN_CATALOG.clear()
    with caplog.at_level(logging.WARNING):
        plugins.load_plugin_catalog()
    assert "PLUGIN_METADATA.license is required" in caplog.text
    assert "ep-no-license" not in plugins.PLUGIN_CATALOG


def test_entry_point_metadata_disallowed_license(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    module = types.ModuleType("ep_bad_license")
    module.PLUGIN_METADATA = {
        "name": "ep-bad-license",
        "version": "0.1.0",
        "interfaces": ["codec"],
        "license": "Proprietary",
    }
    monkeypatch.setitem(sys.modules, "ep_bad_license", module)

    class EP:
        name = "ep_bad_license"
        group = "genecoder.plugins"
        value = "ep_bad_license"

        def load(self) -> types.ModuleType:
            return module

    monkeypatch.setattr(
        plugins,
        "entry_points",
        lambda group=None: [EP()] if group in (None, "genecoder.plugins") else [],
    )
    plugins.PLUGIN_CATALOG.clear()
    with caplog.at_level(logging.WARNING):
        plugins.load_plugin_catalog()
    assert "PLUGIN_METADATA.license 'Proprietary' is not allowed" in caplog.text
    assert "ep-bad-license" not in plugins.PLUGIN_CATALOG


def test_local_plugin_missing_license(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    module = types.ModuleType("plugins")
    module.PLUGIN_METADATA = {
        "name": "local-no-license",
        "version": "0.1.0",
        "interfaces": ["codec"],
    }
    monkeypatch.setitem(sys.modules, "plugins", module)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])
    plugins.PLUGIN_CATALOG.clear()
    with caplog.at_level(logging.WARNING):
        plugins.load_plugin_catalog()
    assert "PLUGIN_METADATA.license is required" in caplog.text
    assert "local-no-license" not in plugins.PLUGIN_CATALOG


def test_local_plugin_disallowed_license(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    module = types.ModuleType("plugins")
    module.PLUGIN_METADATA = {
        "name": "local-bad-license",
        "version": "0.1.0",
        "interfaces": ["codec"],
        "license": "Proprietary",
    }
    monkeypatch.setitem(sys.modules, "plugins", module)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])
    plugins.PLUGIN_CATALOG.clear()
    with caplog.at_level(logging.WARNING):
        plugins.load_plugin_catalog()
    assert "PLUGIN_METADATA.license 'Proprietary' is not allowed" in caplog.text
    assert "local-bad-license" not in plugins.PLUGIN_CATALOG
