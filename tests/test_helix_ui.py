import pytest
from urllib.parse import urlparse
from pathlib import Path

ft = pytest.importorskip("flet")

from genecoder.helix_view import show_helix_ui


def test_show_helix_ui_url(tmp_path: Path) -> None:
    webview = show_helix_ui("ACGT", animate=False, zoom=1.5)
    assert webview.__class__.__name__ == "WebView"
    assert webview.url.startswith("file:")
    parsed = urlparse(webview.url)
    assert "animate=false" in parsed.query
    assert "zoom=1.5" in parsed.query


def test_helix_ui_screenshot(tmp_path: Path) -> None:
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    webview = show_helix_ui("ACGT")
    screenshot = tmp_path / "shot.png"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(webview.url)
        page.screenshot(path=screenshot)
        browser.close()

    assert screenshot.is_file()
