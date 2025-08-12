import os
from pathlib import Path

import yaml
import pytest

from tests.test_cli import run_cli_command
from genecoder.simulators.nanopore import NanoporeDNArSimChannel


def test_pipeline_cli_profile_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = os.environ.copy()
    src_path = Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    input_file = tmp_path / "msg.txt"
    input_file.write_text("hi")
    output_file = tmp_path / "out.txt"

    config = {
        "codec": "reverse",
        "channel": {"name": "nanopore_dnarsim", "profile": "r10.3"},
    }
    cfg_path = tmp_path / "pipe.yml"
    cfg_path.write_text(yaml.safe_dump(config))

    called: list[str | None] = []

    def fake_simulate(self: NanoporeDNArSimChannel, seq: str) -> str:
        called.append(self.profile)
        return seq

    monkeypatch.setattr(NanoporeDNArSimChannel, "simulate", fake_simulate)

    result = run_cli_command(
        ["pipeline", str(input_file), str(output_file), "--config", str(cfg_path)], env=env
    )
    assert result.returncode == 0, result.stderr
    assert called == ["r10.3"]
    assert output_file.read_text() == "hi"
