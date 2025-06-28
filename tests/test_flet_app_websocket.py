import asyncio
import importlib
import sys
import types
import logging

import pytest

ft = pytest.importorskip("flet")


def test_websocket_start_error_logged(monkeypatch, caplog):
    dummy_ws = types.SimpleNamespace(
        serve=lambda *a, **k: (_ for _ in ()).throw(OSError("boom"))
    )
    monkeypatch.setitem(sys.modules, "websockets", dummy_ws)

    loop = asyncio.new_event_loop()
    monkeypatch.setattr(asyncio, "get_event_loop", lambda: loop)

    if "genecoder.flet_app" in sys.modules:
        del sys.modules["genecoder.flet_app"]

    with caplog.at_level(logging.ERROR):
        importlib.import_module("genecoder.flet_app")

    assert any(
        "Failed to start WebSocket server" in rec.message for rec in caplog.records
    )
