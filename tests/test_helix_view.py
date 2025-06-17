

if not hasattr(ft, "HtmlElement"):
    pytest.skip("HtmlElement not available", allow_module_level=True)

ft = pytest.importorskip("flet")

def test_show_helix_basic() -> None:
    from genecoder.helix_view import show_helix

    elem = show_helix()
    assert elem.__class__.__name__ == "WebView"
    assert elem.width == 600
    assert elem.height == 400
    assert elem.url.startswith("data:text/html,")
