from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests.test_cli import run_cli_command

yaml = pytest.importorskip("yaml")
if yaml.safe_load("test: value") == {}:
    pytest.skip("PyYAML required for decay channel config test", allow_module_level=True)


def test_channel_decay_config(tmp_path: Path) -> None:
    config_src = Path("configs/decay_demo.yaml")
    work_dir = tmp_path
    encoded_dir = work_dir / "encoded"
    encoded_dir.mkdir()

    input_payload = Path("tests/data/vertical_slice.txt")
    env = os.environ.copy()
    env["GENECODER_SIM_SEED"] = "12345"

    encode_result = run_cli_command(
        [
            "encode",
            "--input-files",
            str(input_payload),
            "--output-dir",
            str(encoded_dir),
            "--method",
            "base4_direct",
        ],
        env=env,
    )
    assert encode_result.returncode == 0, encode_result.stderr

    encoded_fasta = encoded_dir / "vertical_slice.txt.fasta"
    assert encoded_fasta.exists(), "Encoded FASTA missing"

    message_fasta = encoded_dir / "message.fasta"
    message_fasta.write_bytes(encoded_fasta.read_bytes())

    cfg_path = work_dir / config_src.name
    config_data = yaml.safe_load(config_src.read_text(encoding="utf-8"))
    config_data["input"] = str(message_fasta)
    output_fasta = work_dir / "decay_output.fasta"
    config_data["output"] = str(output_fasta)
    cfg_path.write_text(yaml.safe_dump(config_data, sort_keys=False), encoding="utf-8")

    channel_env = env.copy()
    run_result = run_cli_command(["channel", "run", str(cfg_path)], env=channel_env)
    assert run_result.returncode == 0, run_result.stderr

    assert output_fasta.exists(), "Channel output FASTA missing"
    manifest_path = output_fasta.with_suffix(".manifest.json")
    assert manifest_path.exists(), "Manifest missing"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    simulators = manifest.get("simulators", [])
    sim_names = {str(name).lower() for name in simulators}
    assert any("illumina" in name for name in sim_names), "Illumina simulator not recorded"
    assert any("decay" in name or "degradation" in name for name in sim_names), "Decay simulator not recorded"

    stages = manifest.get("stages")
    assert isinstance(stages, list) and stages, "Stage metadata missing"
    stage_names = {str(stage.get("name", "")).lower() for stage in stages}
    assert any("illumina" in name for name in stage_names), "Illumina stage missing"
    assert any("decay" in name or "degrad" in name for name in stage_names), "Decay stage missing"
