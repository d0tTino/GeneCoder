from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_check_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_init_export_duplicates.py"
    spec = spec_from_file_location("check_init_export_duplicates", script_path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_init_export_duplicates_check_passes_for_repo() -> None:
    checker = _load_check_module()
    assert checker.find_duplicate_exports() == []
