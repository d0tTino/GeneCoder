import sys
from pathlib import Path

# Add the project's root and src directories to sys.path so tests can import the package
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / 'src'

for path in (SRC_PATH, PROJECT_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
