from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_checker_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_capability_docs_sync.py"
    spec = spec_from_file_location("check_capability_docs_sync", script_path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_missing_matrix_paths_valid_and_invalid(tmp_path):
    checker = _load_checker_module()

    (tmp_path / "src/genecoder/cli").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "src/genecoder/cli/cli.py").write_text("", encoding="utf-8")
    (tmp_path / "tests/test_cli.py").write_text("", encoding="utf-8")

    valid_matrix = {
        "capabilities": [
            {
                "id": "valid_capability",
                "owner_modules": ["src/genecoder/cli/cli.py"],
                "validation_artifacts": [{"type": "test", "path": "tests/test_cli.py"}],
            }
        ]
    }
    assert checker._collect_missing_matrix_paths(valid_matrix, tmp_path) == []

    invalid_matrix = {
        "capabilities": [
            {
                "id": "invalid_capability",
                "owner_modules": ["src/genecoder/cli/missing.py"],
                "validation_artifacts": [
                    {"type": "test", "path": "tests/test_missing.py"}
                ],
            }
        ]
    }
    assert checker._collect_missing_matrix_paths(invalid_matrix, tmp_path) == [
        "invalid_capability: owner_modules -> src/genecoder/cli/missing.py",
        "invalid_capability: validation_artifacts.path -> tests/test_missing.py",
    ]
