from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Sequence

import pytest

from tests.test_cli import run_cli_command

pytest.importorskip("jsonschema")
yaml = pytest.importorskip("yaml")
if yaml.safe_load("foo: 1") == {}:
    pytest.skip("Functional YAML parser required for bundle tests", allow_module_level=True)


def _prepare_config(base_dir: Path) -> tuple[Path, dict[str, object], Path]:
    base_config = Path(__file__).resolve().parents[1] / "configs" / "fountain_nanopore_pipeline.yaml"
    config = yaml.safe_load(base_config.read_text(encoding="utf-8")) or {}

    input_file = base_dir / "nanopore_payload.txt"
    input_file.write_text("nanopore fountain bundle")

    encode_cfg = config.get("encode", {}) if isinstance(config, dict) else {}
    if isinstance(encode_cfg, dict):
        encode_cfg["input_files"] = [str(input_file)]
    simulate_cfg = config.get("simulate") if isinstance(config, dict) else None
    if isinstance(simulate_cfg, dict):
        simulate_cfg["seed"] = 7
    trimmed_config = base_dir / "fountain_nanopore.yaml"
    trimmed_config.write_text(yaml.safe_dump(config))
    return trimmed_config, config, input_file


def _bundle_run_with_cache(
    cache_dir: Path,
    config_path: Path,
    config_dict: dict[str, object],
    extra_args: Sequence[str] | None = None,
    env: dict[str, str] | None = None,
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    config_hash = hashlib.sha256(json.dumps(config_dict, sort_keys=True).encode("utf-8")).hexdigest()
    run_root = cache_dir / config_hash
    run_dirs = sorted(run_root.iterdir()) if run_root.exists() else []
    if not run_dirs:
        args: list[str] = ["bundle", "run", str(config_path), "--cache-dir", str(cache_dir)]
        if extra_args:
            args.extend(extra_args)
        result = run_cli_command(args, env=env)
        assert result.returncode == 0, result.stderr
        run_dirs = sorted(run_root.iterdir())
    assert run_dirs, "bundle run directory missing"
    return run_dirs[-1]


@pytest.fixture(scope="session")
def bundle_cache_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    cache_dir = tmp_path_factory.mktemp("bundle_cache")
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


@pytest.fixture(scope="session")
def nanopore_bundle_config(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, object], Path]:
    base_dir = tmp_path_factory.mktemp("nanopore_bundle")
    return _prepare_config(base_dir)


def test_bundle_nanopore_fountain(
    bundle_cache_dir: Path, nanopore_bundle_config: tuple[Path, dict[str, object], Path]
) -> None:
    config_path, config_dict, input_path = nanopore_bundle_config

    run_dir = _bundle_run_with_cache(
        cache_dir=bundle_cache_dir,
        config_path=config_path,
        config_dict=config_dict,
        extra_args=("--emit-manifest-report",),
        env={"GENECODER_SIM_SEED": "7"},
    )

    decoded_dir = run_dir / "decoded"
    decoded_payload = decoded_dir / f"{input_path.name}_decoded.bin"
    manifest_json = decoded_payload.with_suffix(".bin.manifest.json")
    manifest_html = manifest_json.with_suffix(".html")

    assert decoded_payload.exists(), "decoded payload missing"
    assert manifest_json.exists(), "decoded manifest missing"
    assert manifest_html.exists(), "decoded manifest report missing"
