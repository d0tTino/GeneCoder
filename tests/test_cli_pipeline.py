import os
from pathlib import Path
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
