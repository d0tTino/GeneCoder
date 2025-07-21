import pytest
import subprocess
from pathlib import Path

pytest.importorskip("httpx")
from genecoder.cloud.hpc import generate_slurm_script, submit_slurm_job
from genecoder.cloud import CloudClient
from tests.test_cli import run_cli_command


def test_generate_slurm_script() -> None:
    script = generate_slurm_script(
        "echo hi", job_name="tst", time="00:10:00", partition="debug"
    )
    assert "#SBATCH --job-name=tst" in script
    assert "#SBATCH --time=00:10:00" in script
    assert "#SBATCH --partition=debug" in script
    assert "echo hi" in script


@pytest.mark.parametrize(
    "cmd",
    [
        "echo hi && rm -rf /",
        "echo hi; rm -rf /",
        "bad\ncmd",
        "echo hi | wc",
        "echo hi > out.txt",
    ],
)
def test_generate_slurm_script_rejects_bad(cmd: str) -> None:
    with pytest.raises(ValueError):
        generate_slurm_script(cmd)


@pytest.mark.parametrize("job_name", ["bad name", "bad/name", "bad!", "foo$"])
def test_generate_slurm_script_bad_job_name(job_name: str) -> None:
    with pytest.raises(ValueError):
        generate_slurm_script("echo hi", job_name=job_name)


@pytest.mark.parametrize("partition", ["bad part", "bad/part", "bad!", "foo$"])
def test_generate_slurm_script_bad_partition(partition: str) -> None:
    with pytest.raises(ValueError):
        generate_slurm_script("echo hi", partition=partition)


@pytest.mark.parametrize("output", ["bad;out", "bad\nout"])
def test_generate_slurm_script_bad_output(output: str) -> None:
    with pytest.raises(ValueError):
        generate_slurm_script("echo hi", output=output)


def test_submit_slurm_job(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {}

    def fake_run(cmd, *, input=None, text=None, capture_output=None, check=None):
        called["cmd"] = cmd
        called["input"] = input
        class P:
            stdout = "Submitted batch job 123"
        return P()

    monkeypatch.setattr("subprocess.run", fake_run)
    jid = submit_slurm_job("script")
    assert jid == "123"
    assert called["cmd"] == ["sbatch"]
    assert called["input"] == "script"


def test_submit_slurm_job_parse_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd, *, input=None, text=None, capture_output=None, check=None):
        class P:
            stdout = "Job submitted"

        return P()

    monkeypatch.setattr("subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="Failed to parse sbatch output"):
        submit_slurm_job("script")


def test_submit_slurm_job_run_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd, *, input=None, text=None, capture_output=None, check=None):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr("subprocess.run", fake_run)
    with pytest.raises(subprocess.CalledProcessError):
        submit_slurm_job("script")


def test_submit_slurm_job_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd, *, input=None, text=None, capture_output=None, check=None):
        raise FileNotFoundError()

    monkeypatch.setattr("subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="sbatch not found"):
        submit_slurm_job("script")


def test_cloud_client_hpc(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("httpx")
    generated = {}

    def fake_generate(command: str, **kwargs) -> str:
        generated["command"] = command
        generated.update(kwargs)
        return "script"

    def fake_submit(script: str) -> str:
        generated["script"] = script
        return "42"

    monkeypatch.setattr("genecoder.cloud.hpc.generate_slurm_script", fake_generate)
    monkeypatch.setattr("genecoder.cloud.hpc.submit_slurm_job", fake_submit)

    client = CloudClient("http://unused")
    jid = client.submit(
        "hpc",
        {
            "command": "run.sh",
            "job_name": "job",
            "time": "00:05:00",
        },
    )
    assert jid == "42"
    assert generated["command"] == "run.sh"
    assert generated["job_name"] == "job"
    assert generated["time"] == "00:05:00"
    assert generated["script"] == "script"


def test_cloud_cli_hpc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pytest.importorskip("yaml")
    cfg = tmp_path / "job.yml"
    cfg.write_text(
        """command: echo hi
job_name: cli
"""
    )

    called: dict[str, str] = {}

    def fake_generate(command: str, **kwargs) -> str:
        called["command"] = command
        called.update(kwargs)
        return "script"

    def fake_submit(script: str) -> str:
        called["script"] = script
        return "99"

    monkeypatch.setattr("genecoder.cloud.hpc.generate_slurm_script", fake_generate)
    monkeypatch.setattr("genecoder.cloud.hpc.submit_slurm_job", fake_submit)

    result = run_cli_command(["cloud", "submit", "--hpc-config", str(cfg)])
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "99"
    assert called["command"] == "echo hi"
    assert called["job_name"] == "cli"
    assert called["script"] == "script"


@pytest.mark.parametrize(
    "bad", ["echo hi && rm", "bad\ncmd"]
)
def test_cloud_cli_hpc_bad_script(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bad: str
) -> None:
    pytest.importorskip("yaml")
    cfg = tmp_path / "job.yml"
    cfg.write_text(f'script: "{bad}"\n')

    result = run_cli_command(["cloud", "submit", "--hpc-config", str(cfg)])
    assert result.returncode != 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("command", "echo hi && rm"),
        ("job_name", "bad;name"),
        ("partition", "part|ition"),
        ("output", "out.txt && rm"),
    ],
)
def test_cloud_cli_hpc_bad_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str, value: str
) -> None:
    pytest.importorskip("yaml")
    cfg = tmp_path / "job.yml"
    base = {
        "command": "echo hi",
        "job_name": "good",
        "partition": "debug",
    }
    base[field] = value
    cfg.write_text("\n".join(f"{k}: {v}" for k, v in base.items()))

    result = run_cli_command(["cloud", "submit", "--hpc-config", str(cfg)])
    assert result.returncode != 0
