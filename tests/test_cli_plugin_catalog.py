import os
from pathlib import Path
import base64

import pytest
from genecoder.plugin_security import compute_checksum

from tests.test_cli import run_cli_command


class DummyResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def __enter__(self) -> "DummyResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._data


@pytest.mark.usefixtures("tmp_path")
def test_cli_catalog_list_and_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pkg = b"PKG"
    checksum = compute_checksum(pkg)
    sig = base64.b64encode(b"sig").decode()
    catalog = (
        "plugins:\n  - name: plug\n    version: '0.1'\n    url: https://example.com/pkg.whl\n    description: Example\n    checksum: "
        + checksum
        + "\n    signature: "
        + sig
    ).encode()

    patch_dir = tmp_path / "patch"
    patch_dir.mkdir()
    installed = tmp_path / "installed"
    pub_key = patch_dir / "pub.pem"
    site_py = patch_dir / "sitecustomize.py"
    site_py.write_text(
        f"""
import sys
import os
from pathlib import Path
import os
import genecoder.plugin_manager as plugins
import genecoder.cli.plugin as plugin_cli

pkg = {pkg!r}
catalog = {catalog!r}

class _R:
    def __init__(self, data):
        self._data = data
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False
    def read(self):
        return self._data

def fake_urlopen(url, *, timeout=None):
    assert timeout == 30
    if url == 'https://example.com/catalog.yaml':
        return _R(catalog)
    if url == 'https://example.com/pkg.whl':
        return _R(pkg)
    raise AssertionError(url)
plugins.urllib.request.urlopen = fake_urlopen

def fake_check_call(cmd):
    if cmd[:4] == [sys.executable, '-m', 'pip', 'download']:
        dest = cmd[cmd.index('-d') + 1]
        Path(dest).mkdir(parents=True, exist_ok=True)
        (Path(dest) / 'plug.whl').write_bytes(pkg)
    elif cmd[:4] == [sys.executable, '-m', 'pip', 'install']:
        Path('{installed}',).write_text('ok')
    else:
        raise AssertionError(cmd)
plugin_cli.subprocess.check_call = fake_check_call
plugin_cli.plugins.entry_points = lambda group=None: []
from genecoder.plugin_security import compute_checksum as _cc
plugin_cli.plugins.compute_checksum = lambda d, *, signature=None, public_key=None: _cc(d)
plugin_cli.plugins.verify_signature = lambda d, s, k: None
Path('{pub_key}').write_text('PUB')
os.environ['GENECODER_PLUGIN_PUBLIC_KEY'] = '{pub_key}'

"""
    )

    env = os.environ.copy()
    env["GENECODER_PLUGIN_CATALOG_URL"] = "https://example.com/catalog.yaml"
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    env["PYTHONPATH"] = (
        f"{patch_dir}{os.pathsep}{src}" + os.pathsep + env.get("PYTHONPATH", "")
    )

    result = run_cli_command(["plugin", "list"], env=env)
    assert "plug" in result.stdout

    result = run_cli_command(["plugin", "install", "plug"], env=env)
    assert result.returncode == 0
    assert (tmp_path / "installed").is_file()
