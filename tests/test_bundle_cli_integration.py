from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from genecoder.reed_solomon_codec import _HAS_REEDSOLO
from tests.test_cli import run_cli_command

yaml = pytest.importorskip("yaml")


def _prepare_trimmed_config(
    base_config: Path, tmp_path: Path, simulator: str, seed: int = 1
) -> tuple[Path, dict[str, Any], Path]:
    config = yaml.safe_load(base_config.read_text(encoding="utf-8")) or {}

    payload_path = tmp_path / f"{base_config.stem}_payload.txt"
    payload_path.write_text(f"{base_config.stem} bundle payload", encoding="utf-8")

    encode_cfg = config.get("encode", {}) if isinstance(config, dict) else {}
    if isinstance(encode_cfg, dict):
        encode_cfg["input_files"] = [str(payload_path)]
        config["encode"] = encode_cfg

    simulate_cfg = config.get("simulate", {}) if isinstance(config, dict) else {}
    if isinstance(simulate_cfg, dict):
        simulators = simulate_cfg.get("simulators")
        if isinstance(simulators, list):
            simulate_cfg["simulators"] = [simulator]
        else:
            simulate_cfg["simulators"] = [simulator]
        simulate_cfg["seed"] = seed
        pipeline_cfg = simulate_cfg.get("pipeline")
        if isinstance(pipeline_cfg, dict):
            pipeline_cfg.setdefault("coverage_distribution", {1: 1.0})
        else:
            simulate_cfg["pipeline"] = {"coverage_distribution": {1: 1.0}}
        config["simulate"] = simulate_cfg

    trimmed = tmp_path / f"{base_config.stem}_trimmed.yaml"
    trimmed.write_text(yaml.safe_dump(config), encoding="utf-8")
    return trimmed, config, payload_path


def _run_bundle_with_cache(
    config_path: Path, config_dict: dict[str, Any], cache_dir: Path, env: dict[str, str]
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    args = [
        "bundle",
        "run",
        str(config_path),
        "--cache-dir",
        str(cache_dir),
        "--emit-manifest-report",
    ]
    result = run_cli_command(args, env=env)
    assert result.returncode == 0, result.stderr

    config_hash = hashlib.sha256(json.dumps(config_dict, sort_keys=True).encode("utf-8"))
    run_root = cache_dir / config_hash.hexdigest()
    run_dirs = sorted(run_root.iterdir())
    assert run_dirs, "no bundle run recorded"
    return run_dirs[-1]


def _verify_decoded_output(run_dir: Path, payload_path: Path) -> None:
    decoded_dir = run_dir / "decoded"
    decoded_file = decoded_dir / f"{payload_path.name}_decoded.bin"
    manifest_json = decoded_file.with_suffix(".bin.manifest.json")
    manifest_html = manifest_json.with_suffix(".html")

    assert decoded_file.exists(), "decoded payload missing"
    assert decoded_file.read_text(encoding="utf-8") == payload_path.read_text(encoding="utf-8")
    assert manifest_json.exists(), "decoded manifest missing"
    assert manifest_html.exists(), "decoded manifest report missing"


@pytest.mark.parametrize(
    "config_name, simulator, requires_reedsolo",
    [
        ("gold", "illumina", True),
        ("rs_illumina_pipeline", "illumina", True),
        ("fountain_nanopore_pipeline", "nanopore", False),
    ],
)
@pytest.mark.skipif(not yaml.safe_load("foo: 1"), reason="Functional YAML parser required")
def test_bundle_cli_roundtrip(
    config_name: str, simulator: str, requires_reedsolo: bool, tmp_path: Path
) -> None:
    if requires_reedsolo and not _HAS_REEDSOLO:
        pytest.skip("reedsolo not installed")

    base_config = Path(__file__).resolve().parents[1] / "configs" / f"{config_name}.yaml"
    config_path, config_dict, payload_path = _prepare_trimmed_config(
        base_config, tmp_path, simulator
    )
    cache_dir = tmp_path / "bundle_cache"
    env = {"GENECODER_SIM_SEED": "3"}

    run_dir = _run_bundle_with_cache(config_path, config_dict, cache_dir, env)

    _verify_decoded_output(run_dir, payload_path)

    encoded_manifest = run_dir / "encoded" / f"{payload_path.name}.manifest.json"
    assert encoded_manifest.exists(), "encoded manifest missing"

    simulated_dir = run_dir / "simulated"
    simulated_manifests = list(simulated_dir.glob("*.manifest.json"))
    if simulated_manifests:
        assert all(manifest.exists() for manifest in simulated_manifests)
    else:
        # Optional simulators may be unavailable in minimal environments.
        assert not any(simulated_dir.iterdir()), "simulated outputs present without manifest"
