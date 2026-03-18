from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "stamp_validated_commits.py"
    spec = spec_from_file_location("stamp_validated_commits", script_path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stamp_content_rewrites_commit_sha() -> None:
    module = _load_module()
    original = "> last_validated_commit: `deadbeef`\n"

    updated, changed = module.stamp_content(original, "0123456789abcdef")

    assert changed is True
    assert updated == "> last_validated_commit: `0123456789abcdef`\n"


def test_stamp_content_is_noop_when_commit_matches() -> None:
    module = _load_module()
    original = "> last_validated_commit: `0123456789abcdef`\n"

    updated, changed = module.stamp_content(original, "0123456789abcdef")

    assert changed is False
    assert updated == original
