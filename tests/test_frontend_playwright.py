import subprocess
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright


def _build_ui() -> Path:
    root = Path(__file__).resolve().parents[1] / "web" / "helix-ui"
    dist = root / "dist"
    if not dist.is_dir():
        subprocess.run(["npm", "install"], cwd=root, check=True)
        subprocess.run(["npm", "run", "build"], cwd=root, check=True)
    return dist / "index.html"


def test_helix_ui_renders() -> None:
    page_path = _build_ui()
    assert page_path.is_file()

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # Browser may not be installed
            pytest.skip(str(exc))
        page = browser.new_page()
        page.goto(page_path.as_uri())
        page.wait_for_selector("canvas")
        browser.close()
