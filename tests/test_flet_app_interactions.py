import asyncio
from pathlib import Path

import pytest

ft = pytest.importorskip("flet")


def _setup_flet(monkeypatch: pytest.MonkeyPatch):
    ft.icons = getattr(ft, "icons", getattr(ft, "Icons", None)) or ft.Icons
    ft.colors = getattr(ft, "colors", getattr(ft, "Colors", None)) or ft.Colors
    for name in [
        "DNA",
        "SEND_AND_ARCHIVE_OUTLINED",
        "UNARCHIVE_OUTLINED",
        "ANALYTICS_OUTLINED",
    ]:
        if not hasattr(ft.icons, name):
            setattr(ft.icons, name, "")
    for attr in [
        "top_left",
        "top_center",
        "top_right",
        "center_left",
        "center",
        "center_right",
        "bottom_left",
        "bottom_center",
        "bottom_right",
    ]:
        if hasattr(ft.alignment, attr):
            setattr(ft.alignment, attr.upper(), getattr(ft.alignment, attr))

    captured: dict[str, ft.ElevatedButton] = {}
    orig_button = ft.ElevatedButton

    def capture_button(*args, **kwargs):
        btn = orig_button(*args, **kwargs)
        if args and args[0] == "Encode":
            captured["encode"] = btn
        elif args and args[0] == "Decode":
            captured["decode"] = btn
        return btn

    monkeypatch.setattr(ft, "ElevatedButton", capture_button)
    orig_tab = ft.Tab
    monkeypatch.setattr(ft, "Tab", lambda *a, disabled=False, **k: orig_tab(*a, **k))

    dummy_page = _DummyPage()

    def fake_app(*, target, view=ft.AppView.FLET_APP, **kwargs):
        assert view == ft.AppView.FLET_APP_HIDDEN
        target(dummy_page)
        return dummy_page

    monkeypatch.setattr(ft, "app", fake_app)

    return captured, dummy_page


class _DummyPage:
    def __init__(self) -> None:
        self.overlay = []

    def add(self, *controls, **kwargs):  # noqa: D401 - minimal stub
        pass

    def update(self, *controls):  # noqa: D401 - minimal stub
        pass


def test_encode_decode_buttons(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured, page = _setup_flet(monkeypatch)
    from genecoder import flet_app

    ft.app(target=flet_app.main, view=ft.AppView.FLET_APP_HIDDEN, port=0)

    encode_cb = captured["encode"].on_click
    decode_cb = captured["decode"].on_click

    enc_vars = {n: c.cell_contents for n, c in zip(encode_cb.__code__.co_freevars, encode_cb.__closure__)}
    dec_vars = {n: c.cell_contents for n, c in zip(decode_cb.__code__.co_freevars, decode_cb.__closure__)}

    input_path = tmp_path / "data.bin"
    input_path.write_bytes(b"A" * 100)
    enc_vars["selected_encode_input_file_path"].current = str(input_path)

    asyncio.run(encode_cb(None))
    assert enc_vars["sequence_analysis_plot_image"].src_base64

    fasta_out = tmp_path / "encoded.fasta"
    fasta_out.write_text(enc_vars["encode_hidden_fasta_content"].value)

    dec_vars["selected_decode_input_file_path"].current = str(fasta_out)
    asyncio.run(decode_cb(None))
    assert "successful" in dec_vars["decode_status_text"].value.lower()


def test_encode_unexpected_error_propagates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured, _ = _setup_flet(monkeypatch)
    from genecoder import flet_app

    def boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(flet_app, "perform_encoding", boom)

    ft.app(target=flet_app.main, view=ft.AppView.FLET_APP_HIDDEN, port=0)

    encode_cb = captured["encode"].on_click
    enc_vars = {n: c.cell_contents for n, c in zip(encode_cb.__code__.co_freevars, encode_cb.__closure__)}

    input_path = tmp_path / "data.bin"
    input_path.write_bytes(b"abc")
    enc_vars["selected_encode_input_file_path"].current = str(input_path)

    with pytest.raises(RuntimeError):
        asyncio.run(encode_cb(None))


def test_decode_unexpected_error_propagates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured, _ = _setup_flet(monkeypatch)
    from genecoder import flet_app

    def boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(flet_app, "perform_decoding", boom)

    ft.app(target=flet_app.main, view=ft.AppView.FLET_APP_HIDDEN, port=0)

    decode_cb = captured["decode"].on_click
    dec_vars = {n: c.cell_contents for n, c in zip(decode_cb.__code__.co_freevars, decode_cb.__closure__)}

    fasta_in = tmp_path / "data.fasta"
    fasta_in.write_text(">seq1\nATGC")
    dec_vars["selected_decode_input_file_path"].current = str(fasta_in)

    with pytest.raises(RuntimeError):
        asyncio.run(decode_cb(None))


def test_encode_value_error_handled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured, _ = _setup_flet(monkeypatch)
    from genecoder import flet_app

    def bad(*_a, **_k):
        raise ValueError("bad input")

    monkeypatch.setattr(flet_app, "perform_encoding", bad)

    ft.app(target=flet_app.main, view=ft.AppView.FLET_APP_HIDDEN, port=0)

    encode_cb = captured["encode"].on_click
    enc_vars = {n: c.cell_contents for n, c in zip(encode_cb.__code__.co_freevars, encode_cb.__closure__)}

    input_path = tmp_path / "data.bin"
    input_path.write_bytes(b"abc")
    enc_vars["selected_encode_input_file_path"].current = str(input_path)

    asyncio.run(encode_cb(None))
    assert "bad input" in enc_vars["encode_status_text"].value


def test_decode_value_error_handled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured, _ = _setup_flet(monkeypatch)
    from genecoder import flet_app

    def bad(*_a, **_k):
        raise ValueError("bad fasta")

    monkeypatch.setattr(flet_app, "perform_decoding", bad)

    ft.app(target=flet_app.main, view=ft.AppView.FLET_APP_HIDDEN, port=0)

    decode_cb = captured["decode"].on_click
    dec_vars = {n: c.cell_contents for n, c in zip(decode_cb.__code__.co_freevars, decode_cb.__closure__)}

    fasta_in = tmp_path / "data.fasta"
    fasta_in.write_text(">seq1\nATGC")
    dec_vars["selected_decode_input_file_path"].current = str(fasta_in)

    asyncio.run(decode_cb(None))
    assert "bad fasta" in dec_vars["decode_status_text"].value
