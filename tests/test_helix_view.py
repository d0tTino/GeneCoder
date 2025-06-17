def _get_ft_and_show_helix():
    ft = pytest.importorskip("flet")
    if not hasattr(ft, "HtmlElement"):
        pytest.skip("Flet HtmlElement not available")
    from genecoder.helix_view import show_helix
    return ft, show_helix



@pytest.mark.skipif(not hasattr(ft, "HtmlElement"), reason="HtmlElement missing")
def test_show_helix_basic():
    ft, show_helix = _get_ft_and_show_helix()


    elem = show_helix()
    assert elem.__class__.__name__ == "WebView"
    assert elem.width == 600
    assert elem.height == 400
    assert elem.url.startswith("data:text/html,")
