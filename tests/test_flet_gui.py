import pytest

ft = pytest.importorskip("flet")


class _DummyPage:
    def __init__(self) -> None:
        self.overlay = []

    def add(self, *args, **kwargs):
        pass

    def update(self, *args, **kwargs):
        pass


def test_main_registers_event_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    ft.icons = getattr(ft, "icons", getattr(ft, "Icons", None)) or ft.Icons
    ft.colors = getattr(ft, "colors", getattr(ft, "Colors", None)) or ft.Colors

    captured: dict[str, ft.ElevatedButton] = {}
    orig_btn = ft.ElevatedButton

    def capture_button(*args, **kwargs):
        btn = orig_btn(*args, **kwargs)
        if args and args[0] == "Encode":
            captured["encode"] = btn
        elif args and args[0] == "Decode":
            captured["decode"] = btn
        return btn

    monkeypatch.setattr(ft, "ElevatedButton", capture_button)

    def fake_app(*, target, view=ft.AppView.FLET_APP, **kwargs):
        page = _DummyPage()
        target(page)
        return page

    monkeypatch.setattr(ft, "app", fake_app)

    from genecoder import flet_app

    ft.app(target=flet_app.main, view=ft.AppView.FLET_APP_HIDDEN, port=0)

    assert callable(captured["encode"].on_click)
    assert callable(captured["decode"].on_click)
