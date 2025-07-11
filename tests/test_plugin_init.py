import os
import pytest

import genecoder.plugin_manager as plugins


def test_cli_init_plugins_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_load() -> None:
        calls.append(True)

    monkeypatch.setattr(plugins, "load_plugins", fake_load)
    plugins._initialized = False
    from genecoder.cli import cli

    cli.build_parser()
    cli.build_parser()

    assert calls == [True]


def test_web_init_plugins_once(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")

    calls = []

    def fake_load() -> None:
        calls.append(True)

    monkeypatch.setattr(plugins, "load_plugins", fake_load)
    plugins._initialized = False

    import importlib
    import sys
    import types

    # Stub optional dependencies used by the web app
    portalocker_stub = types.ModuleType("portalocker")
    portalocker_stub.Lock = lambda *a, **k: open(os.devnull, "w")
    limiter = types.ModuleType("fastapi_limiter")
    limiter.FastAPILimiter = types.SimpleNamespace(
        redis=None, init=lambda *_: None, close=lambda *_: None
    )
    depends = types.ModuleType("fastapi_limiter.depends")
    depends.RateLimiter = lambda *_, **__: (lambda *_: None)
    redis_mod = types.ModuleType("redis.asyncio")
    redis_mod.from_url = lambda *_args, **_kwargs: None
    redis_pkg = types.ModuleType("redis")
    redis_pkg.asyncio = redis_mod
    sys.modules.setdefault("portalocker", portalocker_stub)
    sys.modules.setdefault("fastapi_limiter", limiter)
    sys.modules.setdefault("fastapi_limiter.depends", depends)
    sys.modules.setdefault("redis.asyncio", redis_mod)
    sys.modules.setdefault("redis", redis_pkg)

    web_main = importlib.import_module("web.main")
    web_main.API_TOKEN = "token"
    from fastapi.testclient import TestClient

    with TestClient(web_main.app):
        pass
    with TestClient(web_main.app):
        pass

    assert calls == [True]
