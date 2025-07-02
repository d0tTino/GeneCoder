import sys

import genecoder.plugins as plugins


class DummyResponse:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._data


def test_registry_install(monkeypatch):
    installs = []

    def fake_check_call(cmd):
        installs.append(cmd)

    def fake_urlopen(url):
        assert url == "https://example.com/plugins.yaml"
        data = b"packages:\n  - pkgA>=1.0\n  - pkgB"
        return DummyResponse(data)

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()

    plugins.load_plugins()

    assert installs == [
        [sys.executable, "-m", "pip", "install", "pkgA>=1.0"],
        [sys.executable, "-m", "pip", "install", "pkgB"],
    ]

