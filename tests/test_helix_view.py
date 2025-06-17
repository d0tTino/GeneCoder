import pytest
import flet as ft

if not hasattr(ft, "HtmlElement"):
    pytest.skip("HtmlElement not available", allow_module_level=True)


def test_show_helix_basic() -> None:
    from genecoder.helix_view import show_helix

    elem = show_helix()
    assert isinstance(elem, ft.HtmlElement)
    assert elem.width == 600
    assert elem.height == 400
    assert "helix-container" in elem.content
