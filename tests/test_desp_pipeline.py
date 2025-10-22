from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

from genecoder.api import Codec
from genecoder.core import run_pipeline
from genecoder.encoders import decode_base4_direct, encode_base4_direct
from genecoder.plugin_manager import CODEC_REGISTRY, init_plugins
from genecoder.reed_solomon_codec import _HAS_REEDSOLO
from genecoder.simulators import SIMULATOR_REGISTRY
import genecoder.desp_adapter as desp_adapter
from tests.test_cli import PROJECT_ROOT


class _Base4Codec(Codec):
    def encode(self, data: bytes) -> str:  # type: ignore[override]
        return encode_base4_direct(data)  # type: ignore[return-value]

    def decode(self, encoded: str) -> bytes:  # type: ignore[override]
        return decode_base4_direct(encoded)[0]


@pytest.mark.skipif(not _HAS_REEDSOLO, reason="reedsolo not installed")
def test_desp_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ensure the DeSP preset integrates with run_pipeline using a stub adapter."""

    config_path = PROJECT_ROOT / "configs" / "desp_pipeline.yaml"
    config = yaml.safe_load(config_path.read_text())
    sim_cfg = config["simulate"]["simulators"][0]
    assert sim_cfg["name"] == "desp"
    error_rate = float(sim_cfg["error_rate"])

    calls: list[tuple[str, float]] = []

    def _fake_simulate_adapter(
        command: str,
        sequence: str,
        rate: float,
        rng,
        extra_args=None,
    ) -> str:
        calls.append((command, rate))
        translate = str.maketrans("ACGT", "CGTA")
        return sequence.translate(translate)

    monkeypatch.setattr(desp_adapter, "_simulate_adapter", _fake_simulate_adapter)
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")

    init_plugins()
    CODEC_REGISTRY["base4_direct"] = {
        "encode": _Base4Codec().encode,
        "decode": _Base4Codec().decode,
    }
    SIMULATOR_REGISTRY["desp"] = desp_adapter.DeSPChannel(error_rate=error_rate)

    source_path = PROJECT_ROOT / "examples" / "pipeline_demo_input.txt"
    input_path = tmp_path / "input.txt"
    output_path = tmp_path / "output.bin"
    input_path.write_bytes(source_path.read_bytes())

    result, metrics = run_pipeline(
        "base4_direct", "reed_solomon", "desp", str(input_path), str(output_path)
    )

    assert result == source_path.read_bytes()
    assert output_path.read_bytes() == result
    assert calls and calls[0] == ("desp", error_rate)
    assert isinstance(metrics.get("substitutions"), int)
    assert isinstance(metrics.get("insertions"), int)
    assert isinstance(metrics.get("deletions"), int)
