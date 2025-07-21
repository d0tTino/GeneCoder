import io
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("httpx")
from genecoder.cloud.utils import extract_zip_safely


def _build_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _build_symlink_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zi = zipfile.ZipInfo("link")
        zi.create_system = 3
        zi.external_attr = 0o120777 << 16
        zf.writestr(zi, "target")
    return buf.getvalue()


def test_extract_zip_safely_valid(tmp_path: Path) -> None:
    data = _build_zip({"a.yaml": b"x"})
    extract_zip_safely(data, tmp_path)
    assert (tmp_path / "a.yaml").exists()


def test_extract_zip_safely_bad_path(tmp_path: Path) -> None:
    data = _build_zip({"../evil.yaml": b"x"})
    with pytest.raises(ValueError):
        extract_zip_safely(data, tmp_path)


def test_extract_zip_safely_symlink(tmp_path: Path) -> None:
    data = _build_symlink_zip()
    with pytest.raises(ValueError):
        extract_zip_safely(data, tmp_path)


def test_extract_zip_safely_large(tmp_path: Path) -> None:
    data = _build_zip({"big.bin": b"x" * 2048})
    with pytest.raises(ValueError):
        extract_zip_safely(data, tmp_path, max_file_size=1024)
