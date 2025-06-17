


import flet as ft
import pytest

@pytest.mark.skipif(not hasattr(ft, "HtmlElement"), reason="HtmlElement missing")
def test_show_helix_basic():
    from genecoder.helix_view import show_helix

    elem = show_helix()
    assert isinstance(elem, ft.HtmlElement)
    assert elem.width == 600
    assert elem.height == 400
    assert "helix-container" in elem.content
