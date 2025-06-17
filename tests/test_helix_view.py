import pytest


ft = pytest.importorskip("flet")


def test_show_helix_basic() -> None:
    from genecoder.helix_view import show_helix

    elem = show_helix()
    assert isinstance(elem, ft.HtmlElement)
    assert elem.width == 600
    assert elem.height == 400
    assert "helix-container" in elem.content
