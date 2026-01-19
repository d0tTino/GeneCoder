from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from tests.test_cli import run_cli_command


yaml = pytest.importorskip("yaml")
if yaml.safe_load("foo: 1") == {}:
    pytest.skip("Functional YAML parser required for bundle tests", allow_module_level=True)


PRESET_CONFIGS = [
    (Path("configs/rs_illumina_pipeline.yaml"), 1234),
    (Path("configs/fountain_nanopore_pipeline.yaml"), 5678),
]


def _load_config(config_path: Path) -> dict[str, object]:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _prepare_config(
    tmp_path: Path,
    base_config_path: Path,
    payload: bytes,
    seed: int,
) -> tuple[Path, dict[str, object], Path]:
    config = _load_config(base_config_path)

    input_file = tmp_path / f"{base_config_path.stem}_payload.bin"
    input_file.write_bytes(payload)

    encode_cfg = config.get("encode", {}) if isinstance(config, dict) else {}
    if not isinstance(encode_cfg, dict):
        encode_cfg = {}
    encode_cfg["input_files"] = [str(input_file)]
    encode_cfg["gc_min"] = 0.0
    encode_cfg["gc_max"] = 1.0
    encode_cfg["max_homopolymer"] = 1000
    config["encode"] = encode_cfg

    simulate_cfg = config.get("simulate", {}) if isinstance(config, dict) else {}
    if not isinstance(simulate_cfg, dict):
        simulate_cfg = {}
    simulate_cfg["seed"] = seed
    simulate_cfg["synthesis"] = {
        "gc_min": 0.0,
        "gc_max": 1.0,
        "max_homopolymer": 1000,
        "min_length": 1,
        "max_length": 10000,
    }
    simulators = simulate_cfg.get("simulators")
    if isinstance(simulators, list) and simulators:
        first = simulators[0]
        sim_name = first.get("name") if isinstance(first, dict) else first
        if isinstance(sim_name, str):
            sim_entry: dict[str, object] = {"name": sim_name}
            if sim_name.startswith("illumina"):
                sim_entry.update(
                    {
                        "substitution_rate": 0.0,
                        "insertion_rate": 0.0,
                        "deletion_rate": 0.0,
                    }
                )
            elif sim_name.startswith("nanopore"):
                sim_entry.update(
                    {
                        "error_rate": 0.0,
                        "substitution_rate": 0.0,
                        "insertion_rate": 0.0,
                        "deletion_rate": 0.0,
                    }
                )
            simulate_cfg["simulators"] = [sim_entry]
    simulate_cfg["pipeline"] = {}
    config["simulate"] = simulate_cfg

    config_path = tmp_path / base_config_path.name
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return config_path, config, input_file


def _run_bundle(
    tmp_path: Path,
    config_path: Path,
    config_dict: dict[str, object],
    env: dict[str, str],
    *,
    allow_missing_fec: bool = False,
) -> Path:
    cache_dir = tmp_path / "bundle_cache"
    cache_dir.mkdir(exist_ok=True)
    args = ["bundle", "run", str(config_path), "--cache-dir", str(cache_dir)]
    if allow_missing_fec:
        args.append("--allow-missing-fec")
    result = run_cli_command(
        args,
        env=env,
    )
    assert result.returncode == 0, result.stderr

    config_hash = hashlib.sha256(
        json.dumps(config_dict, sort_keys=True).encode("utf-8")
    ).hexdigest()
    run_root = cache_dir / config_hash
    run_dirs = sorted(run_root.iterdir())
    assert run_dirs, "bundle run directory missing"
    return run_dirs[-1]


@pytest.mark.parametrize("config_path, seed", PRESET_CONFIGS)
def test_pipeline_presets_roundtrip_and_manifest(
    tmp_path: Path,
    config_path: Path,
    seed: int,
) -> None:
    payload = b"preset pipeline payload"
    preset_config, config_dict, input_file = _prepare_config(
        tmp_path,
        config_path,
        payload,
        seed,
    )

    env = os.environ.copy()
    env["GENECODER_SIM_SEED"] = str(seed)

    run_dir = _run_bundle(tmp_path, preset_config, config_dict, env, allow_missing_fec=True)
    decoded_dir = run_dir / "decoded"
    decoded_file = decoded_dir / f"{input_file.name}_decoded.bin"

    assert decoded_file.exists(), "decoded payload missing"
    assert decoded_file.read_bytes() == payload

    manifest_path = decoded_file.with_suffix(".bin.manifest.json")
    assert manifest_path.exists(), "decoded manifest missing"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metrics = manifest.get("metrics", {})

    assert isinstance(metrics.get("gc_content"), (int, float))
    assert isinstance(metrics.get("max_homopolymer"), int)

    channel_metrics = metrics.get("channel", {})
    mutation_totals = channel_metrics.get("mutation_totals", {})
    for key in ("substitutions", "insertions", "deletions"):
        assert isinstance(mutation_totals.get(key), int)
