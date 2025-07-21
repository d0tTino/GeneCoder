import sys
import os
from pathlib import Path
import pytest

# Add the project's root and src directories to sys.path so tests can import the package
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / 'src'

for path in (SRC_PATH, PROJECT_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)




@pytest.fixture
def large_binary_file(tmp_path: Path) -> tuple[Path, bytes]:
    """Create a binary file larger than 5 MB and return its path and contents."""
    data = os.urandom(6 * 1024 * 1024)
    file_path = tmp_path / "large.bin"
    file_path.write_bytes(data)
    return file_path, data
