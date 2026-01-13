import importlib.util
from pathlib import Path

import pytest

from tests.test_cli import run_cli_command

yaml = pytest.importorskip("yaml")


def test_bundle_reedsolo_missing_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original_find_spec = importlib.util.find_spec

    def _fake_find_spec(name: str, *args, **kwargs):
        if name == "reedsolo":
            return None
        return original_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", _fake_find_spec)

    input_file = tmp_path / "payload.txt"
    input_file.write_text("bundle payload")

    config = {
        "encode": {
            "input_files": [str(input_file)],
            "method": "base4_direct",
            "fec": "reed_solomon",
        },
        "decode": {"method": "base4_direct"},
    }
    cfg_path = tmp_path / "bundle.yaml"
    cfg_path.write_text(yaml.safe_dump(config))

    result = run_cli_command(
        ["bundle", "run", str(cfg_path), "--cache-dir", str(tmp_path / "runs")]
    )

    assert result.returncode != 0
    assert (
        "Reed-Solomon FEC requires the 'reedsolo' package" in result.stderr
    ), result.stderr
