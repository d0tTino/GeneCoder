from __future__ import annotations

from dataclasses import dataclass, field
import copy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from genecoder.channel_config import ChannelConfig
from genecoder.constraints import load_constraint_policy
from genecoder.profiles.registry import (
    LegacyProfilePolicy,
    VersionedProfile,
    policy_from_legacy_flag,
    resolve_channel_profile_alias as _resolve_channel_profile_alias,
    resolve_versioned_profile as _resolve_versioned_profile,
    validate_profile_schema as _validate_profile_schema,
)
from genecoder.simulators.batch_utils import load_coverage_distribution

try:  # pragma: no cover - optional dependency
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import best_match
except Exception:  # pragma: no cover - optional dependency
    Draft202012Validator = None  # type: ignore[assignment]
    best_match = None  # type: ignore[assignment]


CONSTRAINT_ALIASES: dict[str, str] = {
    "homopolymer_max": "max_homopolymer",
}

PIPELINE_ALIASES: dict[str, str] = {
    "threads": "workers",
    "processes": "workers",
}


@dataclass(frozen=True)
class SimulatorStageConfig:
    name: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    stage: str | None = None
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConstraintConfig:
    min_length: int | None = None
    max_length: int | None = None
    max_homopolymer: int | None = None
    gc_min: float = 0.0
    gc_max: float = 1.0

    def to_policy_dict(self) -> dict[str, float | int]:
        raw: dict[str, float | int] = {"gc_min": self.gc_min, "gc_max": self.gc_max}
        if self.min_length is not None:
            raw["min_length"] = self.min_length
        if self.max_length is not None:
            raw["max_length"] = self.max_length
        if self.max_homopolymer is not None:
            raw["max_homopolymer"] = self.max_homopolymer
        return load_constraint_policy(raw, fallback={"gc_min": 0.0, "gc_max": 1.0}).to_dict()


@dataclass(frozen=True)
class PipelineRunSettings:
    parallel: bool = False
    workers: int | None = None
    use_process_pool: bool = False
    use_mpi: bool = False
    illumina_profile: str | None = None
    nanopore_profile: str | None = None
    dropout_rate: float | None = None
    coverage_distribution: Mapping[str, float] | None = None
    synthesis_loss: float | None = None

    def to_channel_config(self) -> ChannelConfig:
        return ChannelConfig(
            parallel=self.parallel,
            workers=self.workers,
            use_process_pool=self.use_process_pool,
            use_mpi=self.use_mpi,
            illumina_profile=self.illumina_profile,
            nanopore_profile=self.nanopore_profile,
            dropout_rate=self.dropout_rate,
            coverage_distribution=(
                dict(self.coverage_distribution) if self.coverage_distribution else None
            ),
            synthesis_loss=self.synthesis_loss,
        )


@dataclass(frozen=True)
class ChannelWorkflowConfig:
    simulators: tuple[SimulatorStageConfig, ...]
    constraints: ConstraintConfig
    pipeline: PipelineRunSettings
    input_file: str | None = None
    output_file: str | None = None
    sub_prob: float = 0.0
    ins_prob: float = 0.0
    del_prob: float = 0.0
    seed: int | None = None
    batch_workers: int | None = None
    decay_rate: float | None = None


def _load_yaml_module() -> object:
    try:
        import yaml

        return yaml
    except Exception:  # pragma: no cover
        from genecoder.plugin_manager import yaml as yaml_module

        if yaml_module is None:
            raise
        return yaml_module


def load_mapping_file(path: str | Path) -> Mapping[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        yaml_mod = _load_yaml_module()
        try:
            data = yaml_mod.safe_load(text)
        except Exception as exc:  # pragma: no cover
            raise ValueError(f"Invalid config in {path}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise ValueError("Config file must map keys to values")
    return dict(data)


def validate_profile_schema(profile: Mapping[str, Any], *, kind: str) -> VersionedProfile:
    return _validate_profile_schema(profile, kind=kind)


def resolve_profile(
    value: str | Mapping[str, Any] | None,
    *,
    kind: str,
    presets: Mapping[str, VersionedProfile],
    allow_legacy_dict: bool = False,
    policy: LegacyProfilePolicy | None = None,
) -> VersionedProfile | None:
    effective_policy = policy or policy_from_legacy_flag(allow_legacy_dict=allow_legacy_dict)
    return _resolve_versioned_profile(
        value,
        kind=kind,
        presets=presets,
        policy=effective_policy,
    )



def resolve_channel_profile_alias(alias: str) -> tuple[str, str]:
    return _resolve_channel_profile_alias(alias)


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "configs" / "schema" / "bundle.schema.json"


def _augment_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema = copy.deepcopy(schema)
    defs = schema.setdefault("$defs", {})
    # legacy field aliases still accepted at config boundary
    synth = defs.get("synthesisConstraints")
    if isinstance(synth, dict):
        props = synth.setdefault("properties", {})
        if isinstance(props, dict):
            props.setdefault("homopolymer_max", props.get("max_homopolymer", {"type": ["integer", "null"]}))
    pipe = defs.get("pipeline")
    if isinstance(pipe, dict):
        props = pipe.setdefault("properties", {})
        if isinstance(props, dict):
            props.setdefault("threads", props.get("workers", {"type": ["integer", "null"]}))
            props.setdefault("processes", props.get("workers", {"type": ["integer", "null"]}))
    return schema


def validate_bundle_document(config: Mapping[str, Any]) -> None:
    if Draft202012Validator is None or best_match is None:
        return
    schema = _augment_schema(json.loads(_schema_path().read_text(encoding="utf-8")))
    validator = Draft202012Validator(schema)
    error = best_match(validator.iter_errors(config))
    if error:
        path = ".".join(str(p) for p in error.path)
        loc = path or "<root>"
        raise ValueError(f"Schema validation failed at {loc}: {error.message}")


def _normalize_constraints(raw: Mapping[str, Any]) -> ConstraintConfig:
    normalized = dict(raw)
    for old, new in CONSTRAINT_ALIASES.items():
        if old in normalized and new not in normalized:
            normalized[new] = normalized[old]
    return ConstraintConfig(
        min_length=int(normalized["min_length"]) if normalized.get("min_length") is not None else None,
        max_length=int(normalized["max_length"]) if normalized.get("max_length") is not None else None,
        max_homopolymer=(
            int(normalized["max_homopolymer"]) if normalized.get("max_homopolymer") is not None else None
        ),
        gc_min=float(normalized.get("gc_min", 0.0)),
        gc_max=float(normalized.get("gc_max", 1.0)),
    )


def _normalize_pipeline(raw: Mapping[str, Any]) -> PipelineRunSettings:
    normalized = dict(raw)
    for old, new in PIPELINE_ALIASES.items():
        if old in normalized and new not in normalized:
            normalized[new] = normalized[old]
    return PipelineRunSettings(
        parallel=bool(normalized.get("parallel", False)),
        workers=int(normalized["workers"]) if normalized.get("workers") is not None else None,
        use_process_pool=bool(normalized.get("use_process_pool", False)),
        use_mpi=bool(normalized.get("use_mpi", False)),
        illumina_profile=(str(normalized["illumina_profile"]) if normalized.get("illumina_profile") else None),
        nanopore_profile=(str(normalized["nanopore_profile"]) if normalized.get("nanopore_profile") else None),
        dropout_rate=(float(normalized["dropout_rate"]) if normalized.get("dropout_rate") is not None else None),
        coverage_distribution=load_coverage_distribution(normalized.get("coverage_distribution")),
        synthesis_loss=(float(normalized["synthesis_loss"]) if normalized.get("synthesis_loss") is not None else None),
    )


def _normalize_stage_options(value: object) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        return tuple(chunk for chunk in value.split() if chunk)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return tuple(str(opt) for opt in value if str(opt))
    return (str(value),)


def _normalize_simulators(items: Sequence[Any]) -> tuple[SimulatorStageConfig, ...]:
    stages: list[SimulatorStageConfig] = []
    for item in items:
        if isinstance(item, str):
            stages.append(SimulatorStageConfig(name=item))
            continue
        if not isinstance(item, Mapping):
            raise ValueError("Each simulator must be a string or mapping")
        name = item.get("name")
        if not isinstance(name, str):
            raise ValueError("Simulator mapping must contain a string 'name'")
        params = dict(item)
        params.pop("name", None)
        stage = str(params.pop("stage", params.pop("stage_name", "")) or "") or None
        options_raw = None
        for key in ("options", "stage_options", "flags", "cli_options"):
            if key in params:
                options_raw = params.pop(key)
                break
        stages.append(
            SimulatorStageConfig(
                name=name,
                parameters=params,
                stage=stage,
                options=_normalize_stage_options(options_raw),
            )
        )
    return tuple(stages)


def load_channel_workflow_config(path: str | Path) -> ChannelWorkflowConfig:
    data = load_mapping_file(path)
    # Validate against simulate contract from bundle schema.
    validate_bundle_document({"encode": {"input_files": ["placeholder"], "method": "base4_direct"}, "simulate": data})

    sims_raw = data.get("simulators", [])
    if not isinstance(sims_raw, Sequence) or isinstance(sims_raw, (str, bytes, bytearray)):
        raise ValueError("'simulators' must be a list")
    simulators = _normalize_simulators(sims_raw)

    synth_section = data.get("synthesis", data.get("constraints", {}))
    if not isinstance(synth_section, Mapping):
        raise ValueError("'synthesis' must be a mapping")
    constraints = _normalize_constraints(synth_section)

    pipeline_raw = data.get("pipeline", {})
    if not isinstance(pipeline_raw, Mapping):
        raise ValueError("'pipeline' must be a mapping")
    pipeline = _normalize_pipeline(pipeline_raw)

    decay_rate: float | None = None
    decay_section = data.get("decay")
    if decay_section is not None:
        if not isinstance(decay_section, Mapping):
            raise ValueError("'decay' must be a mapping")
        half_life = float(decay_section.get("half_life", 0.0) or 0.0)
        variation = float(decay_section.get("variation", 0.0) or 0.0)
        if half_life > 0.0:
            decay_rate = 1.0 - 0.5 ** (1.0 / half_life)
            decay_rate = min(max(decay_rate * (1.0 + variation), 0.0), 1.0)

    if data.get("decay_rate") is not None:
        decay_rate = float(data["decay_rate"])

    return ChannelWorkflowConfig(
        simulators=simulators,
        constraints=constraints,
        pipeline=pipeline,
        input_file=(str(data["input"]) if data.get("input") is not None else None),
        output_file=(str(data["output"]) if data.get("output") is not None else None),
        sub_prob=float(data.get("sub_prob", 0.0) or 0.0),
        ins_prob=float(data.get("ins_prob", 0.0) or 0.0),
        del_prob=float(data.get("del_prob", 0.0) or 0.0),
        seed=(int(data["seed"]) if data.get("seed") is not None else None),
        batch_workers=(int(data["batch_workers"]) if data.get("batch_workers") is not None else None),
        decay_rate=decay_rate,
    )
