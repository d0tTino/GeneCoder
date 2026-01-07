import pytest

import genecoder.plugin_manager as plugins

pytest.importorskip("yaml")


class DummyResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._data


from typing import Callable


def _fake_urlopen(data: str) -> Callable[[str], DummyResponse]:
    def _open(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        return DummyResponse(data.encode())

    return _open


@pytest.mark.parametrize("bad", ["bad;rm", "foo bar", "evil&&stuff"])
def test_install_registry_bad_spec(monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
    data = f"packages:\n  - spec: {bad}\n    license: MIT\n    checksum: deadbeef\n"
    monkeypatch.setattr(plugins.urllib.request, "urlopen", _fake_urlopen(data))
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)

    with pytest.raises(ValueError):
        plugins.install_registry_plugins("https://example.com/plugins.yaml", allow_network=True)
