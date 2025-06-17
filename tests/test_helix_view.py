import pytest
from urllib.parse import unquote

ft = pytest.importorskip("flet")
if not hasattr(ft, "HtmlElement"):
    pytest.skip("Flet HtmlElement not available", allow_module_level=True)

from genecoder.helix_view import show_helix


def _get_ft_and_show_helix():
    return ft, show_helix



@pytest.mark.skipif(not hasattr(ft, "HtmlElement"), reason="HtmlElement missing")
def test_show_helix_basic():
    ft, show_helix = _get_ft_and_show_helix()


    elem = show_helix()
    assert elem.__class__.__name__ == "WebView"
    assert elem.width == 600
    assert elem.height == 400
    assert elem.url.startswith("data:text/html,")
    html = unquote(elem.url.split(",", 1)[1])
    assert "cdn.jsdelivr" not in html
    assert "data:application/javascript;base64" in html
