
import asyncio
import pytest

ft = pytest.importorskip("flet")


class _DummyPage:
    def __init__(self) -> None:
        self.overlay = []

    def add(self, *args, **kwargs) -> None:  # noqa: D401 - minimal stub
        pass

    def update(self, *args, **kwargs) -> None:  # noqa: D401 - minimal stub
        pass


def test_flet_app_main_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.set_event_loop(asyncio.new_event_loop())
    called = False

    def fake_app(*, target, view=ft.AppView.FLET_APP, **kwargs):
        nonlocal called
        assert view == ft.AppView.FLET_APP_HIDDEN
        target(_DummyPage())
        called = True

    monkeypatch.setattr(ft, "app", fake_app)

    from genecoder import flet_app

    ft.app(target=flet_app.main, view=ft.AppView.FLET_APP_HIDDEN, port=0)
    assert called
