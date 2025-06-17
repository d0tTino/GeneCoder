import pytest


def _get_ft_and_show_helix():
    ft = pytest.importorskip("flet")
    if not hasattr(ft, "HtmlElement"):
        pytest.skip("Flet HtmlElement not available")
    from genecoder.helix_view import show_helix
    return ft, show_helix


def test_show_helix_basic():
    ft, show_helix = _get_ft_and_show_helix()

    elem = show_helix()
    assert isinstance(elem, ft.HtmlElement)
    assert elem.width == 600
    assert elem.height == 400
    assert "helix-container" in elem.content
