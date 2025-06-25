import pytest
from urllib.parse import unquote

ft = pytest.importorskip("flet")
from genecoder.helix_view import show_helix


from typing import Any, Callable


def _get_ft_and_show_helix() -> tuple[Any, Callable[..., Any]]:
    return ft, show_helix


@pytest.mark.skipif(not hasattr(ft, "HtmlElement"), reason="HtmlElement missing")
def test_show_helix_basic() -> None:
    ft, show_helix = _get_ft_and_show_helix()

    elem = show_helix("ACGT")
    assert elem.__class__.__name__ == "WebView"
    assert elem.width == 600
    assert elem.height == 400
    assert elem.url.startswith("data:text/html,")
    html = unquote(elem.url.split(",", 1)[1])
    assert "cdn.jsdelivr" not in html
    assert "data:application/javascript;base64" in html


@pytest.mark.skipif(not hasattr(ft, "HtmlElement"), reason="HtmlElement missing")
def test_show_helix_sequence_in_html() -> None:
    ft, show_helix = _get_ft_and_show_helix()
    seq = "AACCGGTT"
    elem = show_helix(seq)
    html = unquote(elem.url.split(",", 1)[1])
    assert seq in html


@pytest.mark.skipif(not hasattr(ft, "HtmlElement"), reason="HtmlElement missing")
def test_show_helix_options() -> None:
    ft, show_helix = _get_ft_and_show_helix()
    elem = show_helix("AC", length=5, colors={"A": "#123456"})
    html = unquote(elem.url.split(",", 1)[1])
    assert "ACACA" in html  # sequence repeated to length
    assert "0x123456" in html


@pytest.mark.skipif(not hasattr(ft, "HtmlElement"), reason="HtmlElement missing")
def test_show_helix_pulse_params() -> None:
    ft, show_helix = _get_ft_and_show_helix()
    elem = show_helix("AC", pulse=True, pulse_speed=3.5)
    html = unquote(elem.url.split(",", 1)[1])
    assert "const showPulses = true" in html
    assert "const pulseSpeed = 3.5" in html


@pytest.mark.skipif(not hasattr(ft, "HtmlElement"), reason="HtmlElement missing")
def test_show_helix_fps_param() -> None:
    ft, show_helix = _get_ft_and_show_helix()
    elem = show_helix("AC", fps=30)
    html = unquote(elem.url.split(",", 1)[1])
    assert "const fps = 30" in html


@pytest.mark.skipif(not hasattr(ft, "HtmlElement"), reason="HtmlElement missing")
def test_show_helix_cdn_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    ft, show_helix = _get_ft_and_show_helix()
    monkeypatch.setattr("genecoder.helix_view.THREE_JS_URL", "")
    monkeypatch.setattr("genecoder.helix_view.ORBIT_JS_URL", "")

    elem = show_helix("ACGT")
    html = unquote(elem.url.split(",", 1)[1])
    assert "cdn.jsdelivr" in html
    assert "data:application/javascript;base64" not in html

