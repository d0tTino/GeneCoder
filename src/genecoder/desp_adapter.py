"""Adapter for the optional ``DeSP`` nanopore simulator."""

from __future__ import annotations

import json
import logging
import random
import shutil
from typing import Any, Callable, Mapping

from .plugin_api import Simulator
from .formats import SequenceBatch, from_fasta
from .random_utils import make_rng
from .simulator_utils import (
    _execute_external,
    _parse_env_options,
    _simulate_adapter,
)
from .simulators import register_simulator as _register_simulator
from .simulators.batch_utils import (
    CONFIG_COVERAGE_KEY,
    CONFIG_DROPOUT_KEY,
    CONFIG_SYNTHESIS_KEY,
    clone_batch,
    load_coverage_distribution,
)

logger = logging.getLogger(__name__)

_DESP_STAGE_METADATA_KEY = "desp_stage_config"


class _DeSP:
    """Internal helper to invoke the ``desp`` binary."""

    command = "desp"

    @staticmethod
    def run(sequence: str) -> str:
        """Run ``desp`` on ``sequence`` via :func:`_simulate_adapter`."""

        return simulate_desp(sequence)


def _stringify_metadata_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _parse_header_metadata(header: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for token in header.strip().split():
        if "=" in token:
            key, value = token.split("=", 1)
            metadata[key] = value
    return metadata


def _apply_metadata_dict(
    batch: SequenceBatch, metadata: Mapping[str, Any] | None
) -> None:
    if not isinstance(metadata, Mapping):
        return

    batch_section = metadata.get("batch")
    if isinstance(batch_section, Mapping):
        for key, value in batch_section.items():
            batch.metadata[str(key)] = _stringify_metadata_value(value)

    oligos_section = metadata.get("oligos")
    if isinstance(oligos_section, list):
        for oligo, data in zip(batch.oligos, oligos_section):
            if isinstance(data, Mapping):
                for key, value in data.items():
                    oligo.metadata[str(key)] = _stringify_metadata_value(value)

    for key, value in metadata.items():
        if key in {"batch", "oligos"}:
            continue
        batch.metadata[str(key)] = _stringify_metadata_value(value)


def _merge_batch_records(
    original: SequenceBatch, records: list[tuple[str, str]]
) -> SequenceBatch:
    mutated = clone_batch(original)
    if len(records) != len(mutated.oligos):
        logger.warning(
            "DeSP returned %d records for %d input oligos",
            len(records),
            len(mutated.oligos),
        )

    for idx, oligo in enumerate(mutated.oligos):
        if idx < len(records):
            header, sequence = records[idx]
            oligo.sequence = sequence
            oligo.header = header
            header_meta = _parse_header_metadata(header)
            for key, value in header_meta.items():
                oligo.metadata[key] = value
        else:
            oligo.sequence = ""

    if records:
        batch_meta = _parse_header_metadata(records[0][0])
        for key, value in batch_meta.items():
            mutated.metadata[key] = value

    return mutated


def _normalise_stage_config(
    stage_parameters: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if not isinstance(stage_parameters, Mapping):
        return {}

    normalised: dict[str, dict[str, Any]] = {}
    for stage, options in stage_parameters.items():
        if not isinstance(options, Mapping):
            continue
        stage_key = str(stage).strip().lower().replace("-", "_")
        normalised_options: dict[str, Any] = {}
        for name, value in options.items():
            option_key = str(name).strip().lower().replace("-", "_")
            normalised_options[option_key] = value
        if normalised_options:
            normalised[stage_key] = normalised_options
    return normalised


def _parse_stage_config_value(value: object) -> dict[str, dict[str, Any]]:
    if value is None:
        return {}
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    else:
        data = value
    if not isinstance(data, Mapping):
        return {}
    return _normalise_stage_config(data)  # type: ignore[arg-type]


def _merge_stage_configs(
    *configs: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for config in configs:
        if not isinstance(config, Mapping):
            continue
        for stage, options in config.items():
            if not isinstance(options, Mapping):
                continue
            stage_key = str(stage)
            target = merged.setdefault(stage_key, {})
            for name, value in options.items():
                target[str(name)] = value
    return merged


def _stage_cli_args(stage_config: Mapping[str, Mapping[str, Any]]) -> list[str]:
    args: list[str] = []
    for stage, options in stage_config.items():
        stage_token = stage.replace("_", "-")
        if not isinstance(options, Mapping):
            continue
        for name, value in options.items():
            if value is None:
                continue
            option_token = str(name).replace("_", "-")
            flag = f"--{stage_token}-{option_token}"
            if isinstance(value, bool):
                args.extend([flag, "true" if value else "false"])
            elif isinstance(value, (list, dict)):
                args.extend([flag, json.dumps(value)])
            else:
                args.extend([flag, str(value)])
    return args


def _stage_options(
    stage_config: Mapping[str, Mapping[str, Any]], *names: str
) -> Mapping[str, Any]:
    for name in names:
        key = name.lower().replace("-", "_")
        if key in stage_config:
            return stage_config[key]
    return {}


def _option_float(options: Mapping[str, Any], *names: str) -> float | None:
    for name in names:
        key = name.lower().replace("-", "_")
        if key in options:
            try:
                return float(options[key])
            except (TypeError, ValueError):
                continue
    return None


def _store_stage_config(
    batch: SequenceBatch, stage_config: Mapping[str, Mapping[str, Any]]
) -> None:
    if stage_config:
        batch.metadata[_DESP_STAGE_METADATA_KEY] = json.dumps(stage_config)
    else:
        batch.metadata.pop(_DESP_STAGE_METADATA_KEY, None)


def _nanopore_fallback(
    batch: SequenceBatch,
    error_rate: float,
    stage_config: Mapping[str, Mapping[str, Any]],
) -> SequenceBatch:
    from .simulators.nanopore import NanoporeChannel
    from .simulators.nanopore_batch import simulate_batch as _simulate_nanopore_batch

    prepared = clone_batch(batch)

    synthesis_opts = _stage_options(stage_config, "synthesizer", "synthesis")
    synthesis_loss = _option_float(synthesis_opts, "decay", "loss", "dropout")
    if synthesis_loss is not None:
        prepared.metadata[CONFIG_SYNTHESIS_KEY] = str(synthesis_loss)

    pcr_opts = _stage_options(stage_config, "pcr", "amplification")
    dropout_rate = _option_float(
        pcr_opts, "bias", "dropout", "rate", "dropout_rate"
    )
    if dropout_rate is None:
        seq_opts_for_dropout = _stage_options(stage_config, "sequencer", "sequencing")
        dropout_rate = _option_float(
            seq_opts_for_dropout, "dropout", "dropout_rate"
        )
    if dropout_rate is not None:
        prepared.metadata[CONFIG_DROPOUT_KEY] = str(dropout_rate)

    sequencer_opts = _stage_options(stage_config, "sequencer", "sequencing")
    coverage_value = _option_float(sequencer_opts, "coverage", "depth")
    coverage_distribution = sequencer_opts.get("coverage_distribution")
    if coverage_distribution is not None:
        parsed_dist = load_coverage_distribution(coverage_distribution)
        if parsed_dist:
            prepared.metadata[CONFIG_COVERAGE_KEY] = json.dumps(
                {str(key): value for key, value in parsed_dist.items()}
            )

    profile_value = (
        sequencer_opts.get("profile")
        or sequencer_opts.get("model")
        or sequencer_opts.get("flowcell")
    )

    channel = NanoporeChannel(error_rate=error_rate)
    if profile_value:
        channel = channel.with_profile(str(profile_value))
        channel.error_rate = error_rate
    if coverage_value is not None:
        try:
            channel.coverage = float(coverage_value)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            pass

    mutated = _simulate_nanopore_batch(channel, prepared)
    _store_stage_config(mutated, stage_config)
    mutated.metadata.setdefault("desp_backend", "nanopore_fallback")
    return mutated


def _simulate_desp_batch(
    batch: SequenceBatch,
    error_rate: float,
    rng: random.Random,
    stage_parameters: Mapping[str, Mapping[str, Any]] | None,
) -> SequenceBatch:
    provided_config = _normalise_stage_config(stage_parameters)
    metadata_config = _parse_stage_config_value(
        batch.metadata.get(_DESP_STAGE_METADATA_KEY)
    )
    stage_config = _merge_stage_configs(metadata_config, provided_config)

    extra_args = _stage_cli_args(stage_config)
    command: list[str] = [_DeSP.command, "-e", str(error_rate)]
    if extra_args:
        command.extend(extra_args)
    command.extend(_parse_env_options(_DeSP.command))

    if shutil.which(_DeSP.command):
        try:
            output_text, metadata = _execute_external(
                command, batch.to_fasta()
            )
            records = from_fasta(output_text)
            if not records:
                raise RuntimeError("desp produced no FASTA output")
            mutated = _merge_batch_records(batch, records)
            _apply_metadata_dict(mutated, metadata)
            _store_stage_config(mutated, stage_config)
            return mutated
        except (ValueError, RuntimeError) as exc:
            logger.warning(
                "%s failed: %s; falling back to internal nanopore model",
                _DeSP.command,
                exc,
            )
    else:
        logger.warning(
            "%s not found; falling back to internal nanopore model",
            _DeSP.command,
        )

    return _nanopore_fallback(batch, error_rate, stage_config)


def simulate_desp(
    sequence: str | SequenceBatch,
    error_rate: float = 0.05,
    rng: random.Random | None = None,
    *,
    stage_parameters: Mapping[str, Mapping[str, Any]] | None = None,
) -> str | SequenceBatch:
    """Use ``desp`` if available, else fall back to internal simulators."""

    if rng is None:
        rng = make_rng()

    if isinstance(sequence, SequenceBatch):
        return _simulate_desp_batch(sequence, error_rate, rng, stage_parameters)

    stage_config = _normalise_stage_config(stage_parameters)
    extra_args = _stage_cli_args(stage_config)
    return _simulate_adapter(_DeSP.command, sequence, error_rate, rng, extra_args)


class DeSPChannel(Simulator):
    """Channel wrapper for the optional ``DeSP`` simulator."""

    def __init__(
        self,
        error_rate: float = 0.05,
        *,
        stage_parameters: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self.error_rate = error_rate
        self.stage_parameters = stage_parameters

    def simulate(self, sequence: str | SequenceBatch) -> str | SequenceBatch:
        return simulate_desp(
            sequence,
            error_rate=self.error_rate,
            rng=make_rng(),
            stage_parameters=self.stage_parameters,
        )


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    """Register the ``desp`` simulator."""

    registrar("desp", DeSPChannel())
