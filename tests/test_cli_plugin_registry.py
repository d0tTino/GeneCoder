from tests.test_cli import run_cli_command
import genecoder.plugin_runtime as plugins


def test_install_registry_requires_flag(monkeypatch):
    calls = []
    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setattr(
        plugins,
        "install_registry_plugins",
        lambda url=None, offline=None: calls.append((url, offline)),
    )

    result = run_cli_command(["plugin", "install-registry"])
    assert result.returncode != 0
    assert not calls


def test_install_registry_with_flag(monkeypatch):
    calls = []
    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setattr(
        plugins,
        "install_registry_plugins",
        lambda url=None, offline=None: calls.append((url, offline)),
    )

    result = run_cli_command(["plugin", "install-registry", "--allow-registry"])
    assert result.returncode == 0
    assert calls == [(None, False)]


def test_install_registry_offline_flag(monkeypatch):
    calls = []
    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "./plugins.yaml")
    monkeypatch.setattr(
        plugins,
        "install_registry_plugins",
        lambda url=None, offline=None: calls.append((url, offline)),
    )

    result = run_cli_command(
        ["plugin", "install-registry", "--allow-registry", "--offline"]
    )
    assert result.returncode == 0
    assert calls == [(None, True)]

