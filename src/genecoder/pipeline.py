from __future__ import annotations

"""Simple pipeline for processing sequences step by step."""

import json
from collections.abc import MutableMapping
from pathlib import Path
import warnings
from typing import Any, Callable, Iterable, Mapping, Sequence, Tuple

from .plugin_manager import init_plugins
from .parallel import parallel_map
from .formats import SequenceBatch
from .simulators.batch_utils import (
    RESULT_COVERAGE_KEY,
    RESULT_DROPOUT_FLAG_KEY,
    RESULT_MUTATION_TOTALS_KEY,
)
from . import core
from .simulators.batch_utils import RESULT_COVERAGE_KEY, RESULT_DROPOUT_FLAG_KEY

__all__ = ["SequencePipeline", "run_pipeline"]


def _metadata_flag_true(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def _metadata_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _has_mutations(metadata: Mapping[str, Any]) -> bool:
    value = metadata.get(RESULT_MUTATION_TOTALS_KEY)
    if value in (None, ""):
        return False
    data: Mapping[str, Any] | None
    if isinstance(value, Mapping):
        data = value
    elif isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return False
        if isinstance(parsed, Mapping):
            data = parsed
        else:
            return False
    else:
        return False
    for key in ("substitutions", "insertions", "deletions"):
        try:
            if int(data.get(key, 0)) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


class SequencePipeline:
    """Legacy string-based pipeline wrapper.

    This adapter exists for backwards compatibility with older integrations
    that expected ``SequencePipeline`` to operate on plain strings. New code
    should prefer the SequenceBatch-aware helpers in :mod:`genecoder.core`.
    """

    def __init__(self, steps: Iterable[Callable[[str], str]] | None = None) -> None:
        warnings.warn(
            "SequencePipeline is deprecated; use genecoder.core helpers instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self.steps: list[Callable[[str], str]] = list(steps or [])

    def add_step(self, step: Callable[[str], str]) -> None:
        """Append ``step`` to the pipeline."""
        self.steps.append(step)

    def run(self, sequence: str) -> str:
        """Return ``sequence`` processed by each step."""
        for step in self.steps:
            sequence = step(sequence)
        return sequence

    def run_batch(
        self,
        sequences: Sequence[str],
        *,
        parallel: bool = False,
        workers: int | None = None,
        use_processes: bool = False,
    ) -> list[str]:
        """Apply the pipeline to ``sequences`` optionally in parallel."""
        if parallel:
            return parallel_map(
                self.run,
                sequences,
                workers=workers,
                use_processes=use_processes,
            )
        return [self.run(s) for s in sequences]


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
) -> Tuple[bytes, dict[str, Any], Mapping[str, Any] | None]:
    """Process ``input_path`` through the selected codec, FEC and channel."""

    init_plugins()

    original_data = Path(input_path).read_bytes()
    dna_batch, fec_info = core.encode(codec, fec_backend, original_data)
    if not isinstance(dna_batch, SequenceBatch):
        dna_batch = SequenceBatch.build(
            [
                (
                    f"batch_id={codec}-pipeline oligo_index=1",
                    str(dna_batch),
                )
            ],
            batch_id=f"{codec}-pipeline",
        )

    simulated_batch, subs, ins, dels, coverage = core.simulate(channel, dna_batch)
    if not isinstance(simulated_batch, SequenceBatch):
        simulated_batch = SequenceBatch.build(
            [
                (
                    dna_batch.first_header() or "batch_id=pipeline oligo_index=1",
                    str(simulated_batch),
                )
            ],
            batch_id=dna_batch.batch_id,
        )

    decode_input: SequenceBatch | str = simulated_batch
    survivor_batch = simulated_batch if isinstance(simulated_batch, SequenceBatch) else None
    if survivor_batch is not None:
        filtered = [
            oligo
            for oligo in survivor_batch.oligos
            if not _metadata_flag_true(oligo.metadata.get(RESULT_DROPOUT_FLAG_KEY))
            and not (
                (coverage_val := _metadata_int(oligo.metadata.get(RESULT_COVERAGE_KEY)))
                is not None
                and coverage_val <= 0
            )
            and not _has_mutations(oligo.metadata)
        ]
        if len(filtered) != len(survivor_batch.oligos):
            decode_input = SequenceBatch(
                batch_id=survivor_batch.batch_id,
                metadata=dict(survivor_batch.metadata),
                seed=survivor_batch.seed,
                oligos=list(filtered),
            )
    channel_report: dict[str, Any] | None = None
    dropout_flags: list[bool] = []
    if isinstance(simulated_batch, SequenceBatch):
        channel_report, dropout_flags = _channel_report(simulated_batch)
    if (
        fec_backend == "fountain"
        and channel_report is not None
        and isinstance(fec_info, MutableMapping)
    ):
        channel_report.setdefault("decode_success_rate", 0.0)
        channel_report.setdefault("decode_success", None)
        channel_report.setdefault("status", "pending")
        fec_info["channel"] = channel_report

    try:
        decoded = core.decode(
            codec,
            fec_backend,
            decode_input,
            fec_info,
            survivor_batch=survivor_batch,
        )
    except Exception:
        if (
            fec_backend == "fountain"
            and channel_report is not None
            and isinstance(fec_info, MutableMapping)
        ):
            channel_report["decode_success"] = False
            channel_report["decode_success_rate"] = 0.0
            channel_report["status"] = "failed"
        raise
    Path(output_path).write_bytes(decoded)

    metrics_dict = core.metrics(
        simulated_batch,
        original_data,
        decoded,
        fec_backend,
        subs,
        ins,
        dels,
        coverage,
    )

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

