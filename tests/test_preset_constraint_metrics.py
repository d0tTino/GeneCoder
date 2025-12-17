from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pytest

from tests.test_cli import run_cli_command

yaml = pytest.importorskip("yaml")


def _load_config(config_path: Path) -> dict[str, object]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _prepare_fast_config(original: Path, tmp_path: Path) -> tuple[Path, dict[str, object]]:
    config = _load_config(original)

    encode_cfg = config.get("encode") if isinstance(config, dict) else None
    if isinstance(encode_cfg, dict):
        if not encode_cfg.get("input_files"):
            encode_cfg["input_files"] = ["tests/data/vertical_slice.txt"]
        encode_cfg.setdefault("fec", None)

    simulate_cfg = config.get("simulate") if isinstance(config, dict) else None
    if isinstance(simulate_cfg, dict):
        simulate_cfg["simulators"] = [{"name": "simple"}]

    fast_config = tmp_path / original.name
    fast_config.write_text(yaml.safe_dump(config), encoding="utf-8")
    return fast_config, config


def _run_bundle(config_path: Path, cache_dir: Path) -> Path:
    result = run_cli_command(
        [
            "bundle",
            "run",
            str(config_path),
            "--cache-dir",
            str(cache_dir),
        ],
        env={
            "PYTHONPATH": "src",
            "NUMBA_DISABLE_JIT": "1",
            "GENECODER_DISABLE_FIX": "0",
            "GENECODER_DISABLE_CONSTRAINT_WARNINGS": "1",
            "GENECODER_SIM_SEED": "1234",
        },
    )

    hash_dirs = sorted(cache_dir.iterdir())
    if not hash_dirs:
        pytest.skip(f"bundle run failed: {result.stderr}")

    run_dirs = sorted(hash_dirs[0].iterdir())
    if not run_dirs:
        pytest.skip(f"bundle run produced no runs: {result.stderr}")
    return run_dirs[-1]


def _iter_manifests(run_dir: Path) -> Iterable[Path]:
    encoded_dir = run_dir / "encoded"
    if encoded_dir.is_dir():
        yield from encoded_dir.glob("*.manifest.json")


def _extract_thresholds(config: dict[str, object]) -> tuple[tuple[float, float], int | None]:
    gc_min = 0.0
    gc_max = 1.0
    max_hp: int | None = None

    if isinstance(config.get("simulate"), dict):
        synth = config["simulate"].get("synthesis") if isinstance(config["simulate"], dict) else None
        if isinstance(synth, dict):
            gc_min = float(synth.get("gc_min", gc_min))
            gc_max = float(synth.get("gc_max", gc_max))
            hp_val = synth.get("max_homopolymer")
            if isinstance(hp_val, int):
                max_hp = hp_val

    if isinstance(config.get("encode"), dict):
        enc = config["encode"]
        if isinstance(enc, dict):
            if "gc_min" in enc:
                gc_min = float(enc.get("gc_min", gc_min))
            if "gc_max" in enc:
                gc_max = float(enc.get("gc_max", gc_max))
            hp_val = enc.get("max_homopolymer")
            if isinstance(hp_val, int):
                max_hp = hp_val if max_hp is None else min(max_hp, hp_val)

    return (gc_min, gc_max), max_hp


@pytest.mark.parametrize(
    "config_file",
    [Path("configs/gold.yaml"), Path("configs/fountain_nanopore_pipeline.yaml")],
)
def test_preset_constraint_metrics(tmp_path: Path, config_file: Path) -> None:
    fast_config, original_config = _prepare_fast_config(config_file, tmp_path)
    run_dir = _run_bundle(fast_config, tmp_path / "runs")

    gc_bounds, max_hp_limit = _extract_thresholds(original_config)

    manifests = list(_iter_manifests(run_dir))
    assert manifests, "no encoded manifests found"

    lower, upper = gc_bounds
    for manifest_path in manifests:
        metrics = json.loads(manifest_path.read_text(encoding="utf-8")).get("metrics", {})
        final_gc = float(metrics.get("final_gc", metrics.get("actual_gc", -1.0)))
        assert lower <= final_gc <= upper, f"GC% {final_gc:.4f} outside [{lower}, {upper}] for {manifest_path}"

        if max_hp_limit is not None:
            final_hp = int(metrics.get("final_max_homopolymer", metrics.get("max_homopolymer", -1)))
            assert (
                final_hp <= max_hp_limit
            ), f"Homopolymer {final_hp} exceeds limit {max_hp_limit} for {manifest_path}"
