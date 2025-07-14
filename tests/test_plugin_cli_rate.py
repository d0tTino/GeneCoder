import argparse
import pytest
import sys
from types import SimpleNamespace
from genecoder.cli import plugin as plugin_cli


def test_plugin_rate_cli(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    called = {}

    class DummyResp:
        def __init__(self) -> None:
            self.status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, float]:
            return {"average": 4.0}

    def fake_post(url: str, *, json: dict[str, object], headers: dict[str, str]):
        called["url"] = url
        called["json"] = json
        called["headers"] = headers
        return DummyResp()

    dummy = SimpleNamespace(post=fake_post)
    monkeypatch.setitem(sys.modules, "httpx", dummy)
    args = argparse.Namespace(name="demo", rating=5, server="https://s", token=None)
    plugin_cli._handle_rate(args)
    assert called["url"] == "https://s/plugins/rate"
    assert called["json"] == {"name": "demo", "rating": 5}
    out = capsys.readouterr().out.strip()
    assert out == "4.0"


def test_plugin_rate_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Network failures abort the command."""

    httpx = pytest.importorskip("httpx")

    def fake_post(url: str, *, json: dict[str, object], headers: dict[str, str]):
        raise httpx.ConnectError("offline", request=httpx.Request("POST", url))

    dummy = SimpleNamespace(post=fake_post, HTTPError=httpx.HTTPError)
    monkeypatch.setitem(sys.modules, "httpx", dummy)
    args = argparse.Namespace(name="demo", rating=5, server="https://s", token=None)
    with pytest.raises(SystemExit):
        plugin_cli._handle_rate(args)


def test_plugin_rate_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid JSON responses propagate errors."""

    class DummyResp:
        def __init__(self) -> None:
            self.status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, float]:
            raise ValueError("no json")

    def fake_post(url: str, *, json: dict[str, object], headers: dict[str, str]):
        return DummyResp()

    dummy = SimpleNamespace(post=fake_post, HTTPError=Exception)
    monkeypatch.setitem(sys.modules, "httpx", dummy)
    args = argparse.Namespace(name="demo", rating=5, server="https://s", token=None)
    with pytest.raises(ValueError):
        plugin_cli._handle_rate(args)
