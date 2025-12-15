from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tests.test_cli import run_cli_command

pytest.importorskip("jsonschema")
yaml = pytest.importorskip("yaml")
if yaml.safe_load("foo: 1") == {}:
    pytest.skip("Functional YAML parser required for bundle tests", allow_module_level=True)


def _prepare_config(tmp_path: Path) -> tuple[Path, dict[str, object], Path]:
    base_config = Path(__file__).resolve().parents[1] / "configs" / "fountain_nanopore_pipeline.yaml"
    config = yaml.safe_load(base_config.read_text(encoding="utf-8")) or {}

    input_file = tmp_path / "nanopore_payload.txt"
    input_file.write_text("nanopore fountain bundle")

    encode_cfg = config.get("encode", {}) if isinstance(config, dict) else {}
    if isinstance(encode_cfg, dict):
        encode_cfg["input_files"] = [str(input_file)]
    simulate_cfg = config.get("simulate") if isinstance(config, dict) else None
    if isinstance(simulate_cfg, dict):
        simulate_cfg["seed"] = 7
    trimmed_config = tmp_path / "fountain_nanopore.yaml"
    trimmed_config.write_text(yaml.safe_dump(config))
    return trimmed_config, config, input_file


def test_bundle_nanopore_fountain(tmp_path: Path) -> None:
    cache_dir = tmp_path / "bundle_cache"
    cache_dir.mkdir()

    config_path, config_dict, input_path = _prepare_config(tmp_path)

    result = run_cli_command(
        [
            "bundle",
            "run",
            str(config_path),
            "--cache-dir",
            str(cache_dir),
            "--emit-manifest-report",
        ],
        env={"GENECODER_SIM_SEED": "7"},
    )
    assert result.returncode == 0, result.stderr

    config_hash = hashlib.sha256(json.dumps(config_dict, sort_keys=True).encode("utf-8")).hexdigest()
    run_root = cache_dir / config_hash
    run_dirs = sorted(run_root.iterdir())
    assert run_dirs, "bundle run directory missing"
    run_dir = run_dirs[-1]

    decoded_dir = run_dir / "decoded"
    decoded_payload = decoded_dir / f"{input_path.name}_decoded.bin"
    manifest_json = decoded_payload.with_suffix(".bin.manifest.json")
    manifest_html = manifest_json.with_suffix(".html")

    assert decoded_payload.exists(), "decoded payload missing"
    assert manifest_json.exists(), "decoded manifest missing"
    assert manifest_html.exists(), "decoded manifest report missing"
