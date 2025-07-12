from __future__ import annotations

import io
import os
import stat
import zipfile
from pathlib import Path

__all__ = ["extract_zip_safely"]


def extract_zip_safely(
    data: bytes,
    dest: str | Path,
    *,
    max_file_size: int = 100 * 1024 * 1024,
) -> None:
    """Extract a zip archive with basic security checks.

    The archive is inspected for unsafe paths, symlinks and oversized files
    before extraction. A :class:`ValueError` is raised if any entry violates
    these checks.
    """
    dest_path = Path(dest)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            path = Path(os.path.normpath(info.filename))
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Invalid archive path")

            is_symlink = False
            if hasattr(info, "is_symlink"):
                is_symlink = info.is_symlink()
            else:
                is_symlink = ((info.external_attr >> 16) & 0o170000) == stat.S_IFLNK
            if is_symlink:
                raise ValueError("Invalid archive path")

            if info.file_size > max_file_size:
                raise ValueError("Invalid archive path")

        zf.extractall(dest_path)
