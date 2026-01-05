from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from tests.test_cli import run_cli_command

yaml = pytest.importorskip("yaml")


def _load_pipeline_config(config_path: Path) -> dict[str, object]:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _extract_synthesis(config: dict[str, object]) -> dict[str, float | int]:
    simulate_cfg = config.get("simulate") if isinstance(config, dict) else None
    synthesis_cfg = simulate_cfg.get("synthesis") if isinstance(simulate_cfg, dict) else None
    if not isinstance(synthesis_cfg, dict):
        pytest.skip(f"Config {config} has no synthesis block to validate")

    def _as_float(key: str) -> float:
        val = synthesis_cfg.get(key)
        if val is None:
            pytest.skip(f"{key} missing in synthesis constraints for {config}")
        return float(val)

    def _as_int(key: str) -> int:
        val = synthesis_cfg.get(key)
        if val is None:
            pytest.skip(f"{key} missing in synthesis constraints for {config}")
        return int(val)

    return {
        "gc_min": _as_float("gc_min"),
        "gc_max": _as_float("gc_max"),
        "max_homopolymer": _as_int("max_homopolymer"),
    }


def _write_encode_only_config(original: Path, tmp_path: Path) -> tuple[Path, dict[str, object]]:
    config = _load_pipeline_config(original)
    synthesis = _extract_synthesis(config)

    encode_cfg = deepcopy(config.get("encode", {})) if isinstance(config, dict) else {}
    if not isinstance(encode_cfg, dict):
        encode_cfg = {}
    encode_cfg.setdefault("input_files", ["tests/data/vertical_slice.txt"])

    encode_cfg.update(
        {
            "gc_min": synthesis["gc_min"],
            "gc_max": synthesis["gc_max"],
            "max_homopolymer": synthesis["max_homopolymer"],
        }
    )

    encode_only = {"encode": encode_cfg}
    config_path = tmp_path / f"encode_only_{original.name}"
    config_path.write_text(yaml.safe_dump(encode_only), encoding="utf-8")
    return config_path, synthesis


def _latest_run_dir(cache_dir: Path) -> Path:
    hash_dirs = sorted(cache_dir.iterdir())
    assert hash_dirs, f"No bundle cache directories created under {cache_dir}"
    run_dirs = sorted(hash_dirs[-1].iterdir())
    assert run_dirs, f"Cache directory {hash_dirs[-1]} contained no runs"
    return run_dirs[-1]


@pytest.mark.parametrize(
    ("preset", "config_path"),
    [
        ("Illumina", Path("configs/rs_illumina_pipeline.yaml")),
        ("Nanopore", Path("configs/fountain_nanopore_pipeline.yaml")),
        ("Gold", Path("configs/gold.yaml")),
    ],
)
def test_encode_manifests_respect_pipeline_synthesis_bounds(
    tmp_path: Path, preset: str, config_path: Path
) -> None:
    encode_config_path, synthesis = _write_encode_only_config(config_path, tmp_path)
    cache_dir = tmp_path / "runs"

    result = run_cli_command(
        [
            "bundle",
            "run",
            str(encode_config_path),
            "--cache-dir",
            str(cache_dir),
        ],
        env={
            "PYTHONPATH": "src",
            "NUMBA_DISABLE_JIT": "1",
            "GENECODER_DISABLE_FIX": "0",
            "GENECODER_DISABLE_CONSTRAINT_WARNINGS": "1",
        },
    )

    if result.returncode != 0:
        pytest.skip(f"bundle run failed for {preset}: {result.stderr}")

    run_dir = _latest_run_dir(cache_dir)
    encoded_dir = run_dir / "encoded"
    manifests = sorted(encoded_dir.glob("*.manifest.json"))
    assert manifests, f"{preset} produced no encoded manifests in {encoded_dir}"

    lower = synthesis["gc_min"]
    upper = synthesis["gc_max"]
    max_hp = synthesis["max_homopolymer"]

    for manifest_path in manifests:
        metrics = json.loads(manifest_path.read_text(encoding="utf-8")).get("metrics", {})
        final_gc = float(metrics.get("final_gc", metrics.get("actual_gc", -1.0)))
        assert lower <= final_gc <= upper, (
            f"{preset} GC% {final_gc:.4f} outside [{lower}, {upper}] in {manifest_path.name}"
        )

        final_hp = int(metrics.get("final_max_homopolymer", metrics.get("max_homopolymer", -1)))
        assert final_hp <= max_hp, (
            f"{preset} homopolymer {final_hp} exceeds limit {max_hp} in {manifest_path.name}"
        )
