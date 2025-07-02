import pytest
import json
from pathlib import Path
from flet.core.control_event import ControlEvent

ft = pytest.importorskip("flet")
ft.icons = getattr(ft, "icons", getattr(ft, "Icons", None)) or ft.Icons
ft.colors = getattr(ft, "colors", getattr(ft, "Colors", None)) or ft.Colors


class _DummyPage:
    def __init__(self) -> None:
        self.overlay = []
        self.dialog = None

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


def test_show_helix_ui_returns_webview() -> None:
    from genecoder.helix_view import show_helix_ui

    elem = show_helix_ui("AC")
    assert elem.__class__.__name__ == "WebView"
    assert elem.width == 600
    assert elem.height == 400


def test_glossary_modal_text_opens_dialog() -> None:
    from genecoder.glossary_tooltips import glossary_modal_text

    page = _DummyPage()
    glossary = {"GC content": "short"}
    full = {"GC content": "long definition"}

    txt = glossary_modal_text("GC content", page, glossary, full)

    txt.on_click(None)

    assert isinstance(page.dialog, ft.AlertDialog)
    assert page.dialog.open is True
    assert page.dialog.title.value == "GC content"
    assert page.dialog.content.value == "long definition"


def test_drop_target_invokes_visualizer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ft.icons = getattr(ft, "icons", getattr(ft, "Icons", None)) or ft.Icons
    ft.colors = getattr(ft, "colors", getattr(ft, "Colors", None)) or ft.Colors

    page = _DummyPage()
    monkeypatch.setattr(ft, "app", lambda *, target, view=ft.AppView.FLET_APP, **__: target(page))

    captured_slider: dict[str, ft.Slider] = {}
    orig_slider = ft.Slider

    def capture_slider(*args, **kwargs):
        slider = orig_slider(*args, **kwargs)
        if kwargs.get("divisions") == 15 and kwargs.get("max") == 2.0:
            captured_slider["zoom"] = slider
        return slider

    monkeypatch.setattr(ft, "Slider", capture_slider)
    monkeypatch.setattr("genecoder.flet_app.show_helix_ui", lambda *_, **__: calls.append(True))
    from genecoder import flet_app
    calls: list[bool] = []

    ft.app(target=flet_app.main, view=ft.AppView.FLET_APP_HIDDEN, port=0)

    picker: ft.FilePicker = page.overlay[0]
    picker_vars = {n: c.cell_contents for n, c in zip(picker.on_result.__code__.co_freevars, picker.on_result.__closure__)}

    refresh_fn = captured_slider["zoom"].on_change
    refresh_vars = {n: c.cell_contents for n, c in zip(refresh_fn.__code__.co_freevars, refresh_fn.__closure__)}

    fasta = tmp_path / "seq.fasta"
    fasta.write_text(">seq\nACGT")
    data = json.dumps({"files": [{"name": fasta.name, "path": str(fasta), "size": fasta.stat().st_size, "id": 1}]})
    event = ft.FilePickerResultEvent(ControlEvent("x", "y", data, picker, page))
    picker.on_result(event)

    assert picker_vars["encode_selected_input_file_text"].value.startswith("Selected: ")

    refresh_vars["encode_hidden_fasta_content"].value = fasta.read_text()
    refresh_fn(None)

    assert calls
