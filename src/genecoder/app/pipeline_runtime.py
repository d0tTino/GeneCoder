from __future__ import annotations

"""Simple pipeline for processing sequences step by step."""

from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, Mapping, Tuple

from genecoder.plugin_manager import init_plugins
from genecoder.formats import SequenceBatch
from genecoder.simulators.batch_utils import RESULT_COVERAGE_KEY, RESULT_DROPOUT_FLAG_KEY
from genecoder import core
from genecoder.runtime import RunContext, make_run_context

__all__ = ["SequencePipeline", "run_pipeline"]

from genecoder.compat.legacy import SequencePipeline


def _flag_from_metadata(value: object) -> bool:
    """Return ``True`` when ``value`` signals a simulated dropout."""

    if isinstance(value, str):
        raw = value.strip().lower()
        return raw in {"1", "true", "yes", "y"}
    return bool(value)


def _channel_report(batch: SequenceBatch) -> tuple[dict[str, Any], list[bool]]:
    """Return dropout statistics and flags for ``batch``."""

    primaries = batch.primary_oligos() or batch.oligos
    dropout_flags: list[bool] = []
    coverage_values: list[int] = []
    for oligo in primaries:
        dropout_flags.append(_flag_from_metadata(oligo.metadata.get(RESULT_DROPOUT_FLAG_KEY)))
        coverage_val = oligo.metadata.get(RESULT_COVERAGE_KEY)
        try:
            coverage_values.append(int(coverage_val))
        except (TypeError, ValueError):
            continue

    total = len(primaries)
    dropout_count = sum(1 for flag in dropout_flags if flag)
    dropout_fraction = dropout_count / max(1, total) if total else 0.0
    coverage_avg = (
        sum(coverage_values) / len(coverage_values)
        if coverage_values
        else None
    )

    channel_info: dict[str, Any] = {
        "dropout": {
            "count": dropout_count,
            "fraction": dropout_fraction,
        },
        "oligo_count": total,
    }
    if coverage_avg is not None:
        channel_info["coverage"] = {"average": coverage_avg}

    return channel_info, dropout_flags


def run_pipeline(
    codec: str,
    fec_backend: str | None,
    channel: str | None,
    input_path: str,
    output_path: str,
    filter_mutated: bool = False,
    run_context: RunContext | None = None,
) -> Tuple[bytes, dict[str, Any], Mapping[str, Any] | None]:
    """Process ``input_path`` through the selected codec, FEC and channel.

    Args:
        filter_mutated: When ``True``, drop oligos that contain mutation metadata
            before decoding. Defaults to ``False`` so mutated oligos are retained
            unless they are marked as dropouts or have zero coverage.
    """

    init_plugins()

    original_data = Path(input_path).read_bytes()
    runtime_seed_context = run_context or make_run_context()
    runtime = core.run_canonical_pipeline(
        codec,
        fec_backend,
        channel,
        original_data,
        filter_mutated=filter_mutated,
        run_context=runtime_seed_context,
    )

    simulated_batch = runtime.simulated_batch
    channel_source = simulated_batch
    channel_report: dict[str, Any] | None = None
    dropout_flags: list[bool] = []
    channel_report, dropout_flags = _channel_report(channel_source)

    fec_info = runtime.fec_info
    if (
        fec_backend == "fountain"
        and channel_report is not None
        and isinstance(fec_info, MutableMapping)
    ):
        channel_report.setdefault("decode_success_rate", 0.0)
        channel_report.setdefault("decode_success", None)
        channel_report.setdefault("status", "pending")
        fec_info["channel"] = channel_report

    decoded = runtime.decoded
    Path(output_path).write_bytes(decoded)

    metrics_dict = runtime.metrics

    if (
        fec_backend == "fountain"
        and channel_report is not None
        and isinstance(fec_info, MutableMapping)
    ):
        success_rate = float(metrics_dict.get("decode_success_rate") or 0.0)
        channel_report["decode_success_rate"] = success_rate
        channel_report["decode_success"] = success_rate >= 1.0
        channel_report["status"] = "success" if channel_report["decode_success"] else "failed"
        if dropout_flags:
            dropout_count = sum(1 for flag in dropout_flags if flag)
            channel_report.setdefault("dropout", {})
            channel_report["dropout"]["count"] = dropout_count
            channel_report["dropout"]["fraction"] = dropout_count / max(1, len(dropout_flags))

    return decoded, metrics_dict, fec_info
