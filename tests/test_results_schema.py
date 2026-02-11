from __future__ import annotations

from genecoder.results.schema import (
    RUN_SCHEMA_VERSION,
    canonical_to_legacy_metrics,
    compare_runs,
    load_run_schema,
    migrate_run_schema,
    translate_bundle_metrics,
    translate_decode_summary,
    translate_manifest,
)


def test_translate_manifest_to_canonical() -> None:
    run = translate_manifest(
        {
            "file": "sample.bin",
            "encoding_parameters": {"method": "base4_direct"},
            "metrics": {
                "decode_success_rate": 0.9,
                "gc_variance": 0.01,
                "max_homopolymer": 4,
                "dropout_fraction": 0.1,
                "ber": 0.02,
                "throughput": 12.5,
            },
        }
    )
    assert run["schema_version"] == RUN_SCHEMA_VERSION
    assert run["profiles"]["encoding"] == "base4_direct"
    assert run["outcome"]["decode_success_rate"] == 0.9


def test_backward_compatibility_loader_for_manifest() -> None:
    run = load_run_schema(
        {
            "file": "sample.bin",
            "encoding_parameters": {"method": "base4_direct"},
            "metrics": {"substitutions": 2},
        }
    )
    metrics = canonical_to_legacy_metrics(run)
    assert metrics["substitutions"] == 2


def test_translate_bundle_and_decode_summary() -> None:
    bundle = translate_bundle_metrics({"files": 2, "total_original_size": 10, "total_dna_length": 20})
    decode = translate_decode_summary({"decode_success": True, "ber": 0.01, "throughput": 3.0})
    assert bundle["source_format"] == "bundle_metrics"
    assert decode["source_format"] == "decode_summary"


def test_compare_runs_returns_structured_deltas() -> None:
    baseline = translate_decode_summary({"decode_success": True, "ber": 0.01, "throughput": 3.0, "dropout_rate": 0.1, "gc_stress": 0.02, "homopolymer_stress": 5}, run_id="a")
    candidate = translate_decode_summary({"decode_success": False, "ber": 0.02, "throughput": 2.0, "dropout_rate": 0.3, "gc_stress": 0.03, "homopolymer_stress": 6}, run_id="b")

    result = compare_runs(baseline, candidate)
    assert result["baseline_run_id"] == "a"
    metric_delta = result["comparisons"][0]["metrics"]["ber"]
    assert metric_delta["absolute"] == 0.01
    assert result["comparisons"][0]["metrics"]["decode_success"]["changed"] is True


def test_migrate_legacy_payload() -> None:
    migrated = migrate_run_schema({"metrics": {"substitutions": 1}})
    assert migrated["schema_version"] == RUN_SCHEMA_VERSION
