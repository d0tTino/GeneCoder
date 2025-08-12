import logging
from importlib.metadata import EntryPoint
from collections.abc import Callable
from pathlib import Path

import pytest

import genecoder.plugin_manager as plugins


def _make_entry_points(mode: str, entries: list[EntryPoint | object]) -> Callable[..., object]:
    def func(*, group: str | None = None) -> object:
        if mode == "group":
            assert group is not None
            return [e for e in entries if getattr(e, "group", None) == group]
        if group is not None:
            raise TypeError
        if mode == "select":
            class Obj:
                def select(self, *, group: str) -> list[EntryPoint | object]:
                    return [e for e in entries if getattr(e, "group", None) == group]
            return Obj()
        if mode == "dict":
            d: dict[str, list[EntryPoint | object]] = {}
            for e in entries:
                d.setdefault(getattr(e, "group", ""), []).append(e)
            return d
        return entries
    return func


@pytest.mark.parametrize("mode", ["group", "select", "dict", "list"])
def test_missing_module(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, mode: str) -> None:
    ep = EntryPoint(name="missing", value="no_such_module", group="genecoder.plugins")
    monkeypatch.setattr(plugins, "entry_points", _make_entry_points(mode, [ep]))
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    with caplog.at_level(logging.WARNING):
        plugins.load_plugins()
    assert any("codec:no_such_module" in rec.message for rec in caplog.records)
    assert "missing" not in plugins.CODEC_REGISTRY


class BadEntryPoint:
    def __init__(self, name: str, group: str) -> None:
        self.name = name
        self.group = group
        self.value = name

    def load(self) -> object:
        raise ImportError("bad")


@pytest.mark.parametrize("mode", ["group", "select", "dict", "list"])
def test_bad_entry_point(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, mode: str) -> None:
    ep = BadEntryPoint("bad", "genecoder.plugins")
    monkeypatch.setattr(plugins, "entry_points", _make_entry_points(mode, [ep]))
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    with caplog.at_level(logging.WARNING):
        plugins.load_plugins()
    assert any("codec:bad" in rec.message for rec in caplog.records)
    assert "bad" not in plugins.CODEC_REGISTRY


@pytest.mark.parametrize("mode", ["group", "select", "dict", "list"])
def test_duplicate_names(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str) -> None:
    mod1 = tmp_path / "m1.py"
    mod1.write_text(
        """
from typing import Callable, Any
from genecoder.api import Codec

class CodecOne(Codec):
    def encode(self, data: bytes, /, **kwargs: Any) -> str:
        return "one"

    def decode(self, text: str, /, **kwargs: Any) -> bytes:
        return b"one"

def register(register_codec: Callable[[str, type[Codec]], None]) -> None:
    register_codec("dup", CodecOne)
"""
    )
    mod2 = tmp_path / "m2.py"
    mod2.write_text(
        """
from typing import Callable, Any
from genecoder.api import Codec

class CodecTwo(Codec):
    def encode(self, data: bytes, /, **kwargs: Any) -> str:
        return "two"

    def decode(self, text: str, /, **kwargs: Any) -> bytes:
        return b"two"

def register(register_codec: Callable[[str, type[Codec]], None]) -> None:
    register_codec("dup", CodecTwo)
"""
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    ep1 = EntryPoint(name="one", value="m1", group="genecoder.plugins")
    ep2 = EntryPoint(name="two", value="m2", group="genecoder.plugins")
    monkeypatch.setattr(plugins, "entry_points", _make_entry_points(mode, [ep1, ep2]))
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    plugins.load_plugins()
    assert plugins.CODEC_REGISTRY["dup"]["encode"](b"") == "two"
