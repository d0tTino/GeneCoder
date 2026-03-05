import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from tests.test_cli import run_cli_command


def test_cli_pipeline_indel_rates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_file = tmp_path / "data.bin"
    input_file.write_bytes(b"abc")
    output_file = tmp_path / "out.bin"

    called: list[tuple[float, float, float]] = []

    from genecoder.error_simulation import Channel as IndelChannel

    def fake_simulate(self: IndelChannel, seq: str) -> str:
        called.append((self.substitution_prob, self.insertion_prob, self.deletion_prob))
        return seq

    monkeypatch.setattr(IndelChannel, "simulate", fake_simulate)

    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    result = run_cli_command(
        [
            "pipeline",
            str(input_file),
            str(output_file),
            "--codec",
            "reverse",
            "--channel",
            "indel",
            "--sub-rate",
            "0.1",
            "--ins-rate",
            "0.2",
            "--del-rate",
            "0.05",
        ],
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert called == [(0.1, 0.2, 0.05)]
    assert output_file.read_bytes() == b"abc"


def _run_pipeline_with_config(
    tmp_path: Path,
    config_text: str,
    *,
    seed: str = "314159",
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> tuple[Path, dict[str, object]]:
    input_file = tmp_path / "payload.bin"
    input_file.write_bytes(b"genecli pipeline multi-oligo test payload")
    output_file = tmp_path / "decoded.bin"
    config_file = tmp_path / "pipeline.json"
    config_file.write_text(config_text, encoding="utf-8")

    if monkeypatch is not None:
        from genecoder.cli import pipeline as pipeline_module

        def _json_loader(data: object) -> object:
            if hasattr(data, "read"):
                return json.load(data)  # type: ignore[arg-type]
            if data:
                return json.loads(data)  # type: ignore[arg-type]
            return {}

        monkeypatch.setattr(
            pipeline_module,
            "yaml_module",
            SimpleNamespace(safe_load=_json_loader),
            raising=False,
        )

    env = os.environ.copy()
    env["GENECODER_SIM_SEED"] = seed

    result = run_cli_command(
        [
            "pipeline",
            str(input_file),
            str(output_file),
            "--config",
            str(config_file),
        ],
        env=env,
    )
    assert result.returncode == 0, result.stderr

    metrics_path = Path(str(output_file) + ".json")
    metrics_data = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics = metrics_data.get("outcome", {}).get("metrics", metrics_data.get("metrics"))
    assert isinstance(metrics, dict)

    return output_file, metrics


def test_cli_pipeline_illumina_dropout_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, metrics = _run_pipeline_with_config(
        tmp_path,
        config_text=json.dumps(
            {
                "codec": "reverse",
                "channel": {
                    "name": "illumina",
                    "profile": "miseq",
                    "coverage": 3,
                    "dropout_rate": 1.0,
                    "coverage_distribution": {"0": 1.0},
                },
            }
        ),
        seed="271828",
        monkeypatch=monkeypatch,
    )

    dropout_count = metrics.get("dropout_count")
    channel = metrics.get("channel", {})
    assert isinstance(channel, dict)
    channel_dropout = channel.get("dropout", {})
    assert isinstance(channel_dropout, dict)

    if isinstance(dropout_count, (int, float)):
        assert dropout_count >= 0
    if channel_dropout.get("count") is not None:
        assert channel_dropout.get("count") == dropout_count

    oligo_metrics = metrics.get("oligo_metrics", {})
    assert isinstance(oligo_metrics, dict)
    dropout_flags = oligo_metrics.get("dropout_flags")
    coverage_counts = oligo_metrics.get("coverage_counts")
    if dropout_flags is not None:
        assert isinstance(dropout_flags, list)
    if coverage_counts is not None:
        assert isinstance(coverage_counts, list)
    if isinstance(dropout_flags, list) and isinstance(coverage_counts, list):
        assert len(dropout_flags) == len(coverage_counts)

    seq_batch = metrics.get("sequence_batch", {})
    assert isinstance(seq_batch, dict)
    metadata = seq_batch.get("metadata", {})
    assert isinstance(metadata, dict)
    if metadata.get("sim_dropout_total") is not None and dropout_count is not None:
        assert metadata.get("sim_dropout_total") == str(dropout_count)


def test_cli_pipeline_nanopore_dropout_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, metrics = _run_pipeline_with_config(
        tmp_path,
        config_text=json.dumps(
            {
                "codec": "reverse",
                "channel": {
                    "name": "nanopore",
                    "profile": "r9.4",
                    "dropout_rate": 1.0,
                    "coverage_distribution": {"0": 1.0},
                },
            }
        ),
        seed="123456",
        monkeypatch=monkeypatch,
    )

    channel = metrics.get("channel", {})
    assert isinstance(channel, dict)
    channel_dropout = channel.get("dropout", {})
    assert isinstance(channel_dropout, dict)

    if channel_dropout.get("count") is not None:
        assert channel_dropout.get("count") == metrics.get("dropout_count")
    if channel_dropout.get("fraction") is not None:
        assert channel_dropout.get("fraction") == pytest.approx(1.0)

    oligo_metrics = metrics.get("oligo_metrics", {})
    coverage_counts = oligo_metrics.get("coverage_counts")
    dropout_flags = oligo_metrics.get("dropout_flags")
    if coverage_counts is not None:
        assert isinstance(coverage_counts, list)
    if dropout_flags is not None:
        assert isinstance(dropout_flags, list)
    if isinstance(dropout_flags, list) and isinstance(coverage_counts, list):
        assert len(dropout_flags) == len(coverage_counts)

    seq_batch = metrics.get("sequence_batch", {})
    metadata = seq_batch.get("metadata", {}) if isinstance(seq_batch, dict) else {}
    if metadata.get("sim_dropout_total") is not None and metrics.get("dropout_count") is not None:
        assert metadata.get("sim_dropout_total") == str(metrics.get("dropout_count"))


def test_cli_pipeline_profile_flag_precedence_over_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_file = tmp_path / "payload.bin"
    input_file.write_bytes(b"abc")
    output_file = tmp_path / "decoded.bin"
    config_file = tmp_path / "pipeline.json"
    config_file.write_text(
        json.dumps(
            {
                "codec": "reverse",
                "channel": {
                    "name": "illumina",
                    "profile": "hiseq",
                    "illumina_profile": "hiseq",
                },
            }
        ),
        encoding="utf-8",
    )

    from genecoder.app import RunPipelineUseCase
    from genecoder.cli import pipeline as pipeline_module

    captured: list[object] = []

    def _json_loader(data: object) -> object:
        if hasattr(data, "read"):
            return json.load(data)  # type: ignore[arg-type]
        if data:
            return json.loads(data)  # type: ignore[arg-type]
        return {}

    monkeypatch.setattr(
        pipeline_module,
        "yaml_module",
        SimpleNamespace(safe_load=_json_loader),
        raising=False,
    )

    original_execute = RunPipelineUseCase.execute

    def _capture_execute(self: RunPipelineUseCase, request: object):
        captured.append(request)
        return original_execute(self, request)

    monkeypatch.setattr(RunPipelineUseCase, "execute", _capture_execute)

    result = run_cli_command(
        [
            "pipeline",
            str(input_file),
            str(output_file),
            "--config",
            str(config_file),
            "--illumina-profile",
            "miseq",
        ]
    )
    assert result.returncode == 0, result.stderr
    assert captured, "RunPipelineUseCase.execute was not called"
    request = captured[0]
    profile = getattr(request, "profile")
    parameters = getattr(profile, "parameters")
    assert parameters.get("illumina_profile") == "miseq"
    assert parameters.get("profile") == "miseq"


def test_cli_pipeline_nanopore_profile_flag_sets_profile_parameter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_file = tmp_path / "payload.bin"
    input_file.write_bytes(b"abc")
    output_file = tmp_path / "decoded.bin"

    from genecoder.app import RunPipelineUseCase

    captured: list[object] = []
    original_execute = RunPipelineUseCase.execute

    def _capture_execute(self: RunPipelineUseCase, request: object):
        captured.append(request)
        return original_execute(self, request)

    monkeypatch.setattr(RunPipelineUseCase, "execute", _capture_execute)

    result = run_cli_command(
        [
            "pipeline",
            str(input_file),
            str(output_file),
            "--codec",
            "reverse",
            "--channel",
            "nanopore",
            "--nanopore-profile",
            "r10",
        ]
    )
    assert result.returncode == 0, result.stderr
    assert captured, "RunPipelineUseCase.execute was not called"
    request = captured[0]
    profile = getattr(request, "profile")
    parameters = getattr(profile, "parameters")
    assert parameters.get("nanopore_profile") == "r10"
    assert parameters.get("profile") == "r10"
