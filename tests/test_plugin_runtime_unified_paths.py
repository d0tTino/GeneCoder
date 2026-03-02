import argparse

import pytest

import genecoder.plugin_runtime as runtime
from genecoder.cli import plugin as plugin_cli


def test_registry_install_offline_uses_installer_path(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_install(url, *, offline, allow_network, yaml_module, installer):
        calls.append((str(url), bool(offline)))
        assert allow_network is True
        return []

    monkeypatch.setattr(runtime, "yaml", object())
    monkeypatch.setattr(runtime, "_install_registry_plugins", fake_install)
    runtime.install_registry_plugins("https://example.com/plugins.yaml", offline=True, allow_network=True)
    assert calls == [("https://example.com/plugins.yaml", True)]


def test_catalog_plugin_install_uses_unified_spec_installer(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime.PLUGIN_CATALOG.clear()
    runtime.PLUGIN_CATALOG["demo"] = {
        "url": "https://example.com/demo.whl",
        "checksum": "abc",
        "signature": "sig",
    }
    calls: list[tuple[str, str | None, str | None, bool]] = []

    def fake_install(spec: str, *, checksum, signature, allow_network, installer):
        calls.append((spec, checksum, signature, allow_network))
        return spec

    monkeypatch.setattr(runtime, "install_plugin_spec", fake_install)
    monkeypatch.setenv("GENECODER_ALLOW_NETWORK", "1")
    runtime.install_catalog_plugin("demo")

    assert calls == [("https://example.com/demo.whl", "abc", "sig", True)]


def test_cli_plugin_registry_delegates_to_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []

    monkeypatch.setattr(runtime, "install_registry_plugins", lambda **kwargs: called.append(kwargs["offline"]))
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    plugin_cli.register_subcommand(sub)
    args = parser.parse_args(["plugin", "install-registry", "--allow-registry", "--offline"])
    args.func(args)

    assert called == [True]
