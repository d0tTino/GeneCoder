from __future__ import annotations

import json
from copy import deepcopy
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
    cache_dir.mkdir(parents=True, exist_ok=True)
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


def _iter_simulated_manifests(run_dir: Path) -> Iterable[Path]:
    simulated_dir = run_dir / "simulated"
    if simulated_dir.is_dir():
        yield from simulated_dir.glob("*.manifest.json")


def _read_manifest_metrics(manifest_path: Path) -> dict[str, object]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return data.get("metrics", data)


def _parse_constraint_values(raw: dict[str, object]) -> dict[str, float | int]:
    constraints: dict[str, float | int] = {}
    for key in ("gc_min", "gc_max"):
        if key in raw:
            constraints[key] = float(raw[key])
    for key in ("max_homopolymer", "min_length", "max_length"):
        if key in raw:
            constraints[key] = int(raw[key])
    return constraints


def _collect_summary_constraints(run_dir: Path) -> list[dict[str, float | int]]:
    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        return []

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    batches = summary.get("sequence_batches", {}) if isinstance(summary, dict) else {}
    constraints: list[dict[str, float | int]] = []
    for batch in batches.values():
        metadata = batch.get("metadata", {}) if isinstance(batch, dict) else {}
        constraints.append(_parse_constraint_values(metadata))
    return constraints


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
        metrics = _read_manifest_metrics(manifest_path)
        final_gc = float(metrics.get("final_gc", metrics.get("actual_gc", -1.0)))
        assert lower <= final_gc <= upper, f"GC% {final_gc:.4f} outside [{lower}, {upper}] for {manifest_path}"

        if max_hp_limit is not None:
            final_hp = int(metrics.get("final_max_homopolymer", metrics.get("max_homopolymer", -1)))
            assert (
                final_hp <= max_hp_limit
            ), f"Homopolymer {final_hp} exceeds limit {max_hp_limit} for {manifest_path}"

    simulate_cfg = original_config.get("simulate") if isinstance(original_config, dict) else None
    synthesis_cfg = simulate_cfg.get("synthesis") if isinstance(simulate_cfg, dict) else {}

    expected_min_len = int(synthesis_cfg.get("min_length", 25))
    expected_max_len = int(synthesis_cfg.get("max_length", 300))
    synth_gc_min = float(synthesis_cfg.get("gc_min", lower))
    synth_gc_max = float(synthesis_cfg.get("gc_max", upper))

    constraint_sources: list[dict[str, float | int]] = []

    for sim_manifest in _iter_simulated_manifests(run_dir):
        sim_data = json.loads(sim_manifest.read_text(encoding="utf-8"))
        constraints = _parse_constraint_values(sim_data.get("constraints", {}))
        if constraints:
            constraint_sources.append(constraints)

    constraint_sources.extend(_collect_summary_constraints(run_dir))
    assert constraint_sources, "no constraint metadata available for validation"

    for constraints in constraint_sources:
        gc_min_val = float(constraints.get("gc_min", lower))
        gc_max_val = float(constraints.get("gc_max", upper))

        assert gc_min_val == pytest.approx(lower) or gc_min_val == pytest.approx(
            synth_gc_min
        )
        assert gc_max_val == pytest.approx(upper) or gc_max_val == pytest.approx(
            synth_gc_max
        )
        assert int(constraints.get("min_length", expected_min_len)) == expected_min_len
        assert int(constraints.get("max_length", expected_max_len)) == expected_max_len
        if max_hp_limit is not None:
            assert int(constraints.get("max_homopolymer", max_hp_limit)) == max_hp_limit


def test_constraint_metrics_change_with_synthesis_thresholds(tmp_path: Path) -> None:
    fast_config, _ = _prepare_fast_config(Path("configs/gold.yaml"), tmp_path)
    base_cfg = _load_config(fast_config)

    def _write_variant(name: str, gc_min: float, gc_max: float, max_hp: int) -> tuple[Path, dict[str, object]]:
        config_variant = deepcopy(base_cfg)
        simulate_cfg = config_variant.setdefault("simulate", {})
        synthesis_cfg = simulate_cfg.setdefault("synthesis", {})
        synthesis_cfg.update(
            {
                "gc_min": gc_min,
                "gc_max": gc_max,
                "max_homopolymer": max_hp,
            }
        )
        variant_path = tmp_path / f"{fast_config.stem}_{name}{fast_config.suffix}"
        variant_path.write_text(yaml.safe_dump(config_variant), encoding="utf-8")
        return variant_path, config_variant

    tight_path, tight_cfg = _write_variant("tight", 0.48, 0.52, 2)
    loose_path, loose_cfg = _write_variant("loose", 0.30, 0.70, 8)

    tight_run = _run_bundle(tight_path, tmp_path / "runs_tight")
    loose_run = _run_bundle(loose_path, tmp_path / "runs_loose")

    tight_manifests = list(_iter_manifests(tight_run))
    loose_manifests = list(_iter_manifests(loose_run))
    assert tight_manifests and loose_manifests

    tight_constraints = _collect_summary_constraints(tight_run)
    loose_constraints = _collect_summary_constraints(loose_run)

    if not tight_constraints:
        tight_constraints = [
            _parse_constraint_values(
                json.loads(manifest.read_text(encoding="utf-8")).get("constraints", {})
            )
            for manifest in _iter_simulated_manifests(tight_run)
        ]

    if not loose_constraints:
        loose_constraints = [
            _parse_constraint_values(
                json.loads(manifest.read_text(encoding="utf-8")).get("constraints", {})
            )
            for manifest in _iter_simulated_manifests(loose_run)
        ]

    assert tight_constraints and loose_constraints, "no constraint data available for comparison"

    def _assert_matches(cfg: dict[str, object], constraints: dict[str, float | int]) -> None:
        synth_cfg = (
            cfg.get("simulate", {}).get("synthesis") if isinstance(cfg.get("simulate"), dict) else {}
        )
        assert constraints, "Metrics did not record synthesis constraint limits"
        assert float(constraints.get("gc_min", -1.0)) == pytest.approx(float(synth_cfg["gc_min"]))
        assert float(constraints.get("gc_max", -1.0)) == pytest.approx(float(synth_cfg["gc_max"]))
        assert int(constraints.get("max_homopolymer", -1)) == int(synth_cfg["max_homopolymer"])

    _assert_matches(tight_cfg, tight_constraints[0])
    _assert_matches(loose_cfg, loose_constraints[0])

    assert tight_constraints[0] != loose_constraints[0], "Metrics did not change after adjusting constraints"
