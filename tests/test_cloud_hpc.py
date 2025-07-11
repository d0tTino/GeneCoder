import pytest

from genecoder.cloud.hpc import generate_slurm_script, submit_slurm_job
from genecoder.cloud import CloudClient


def test_generate_slurm_script() -> None:
    script = generate_slurm_script(
        "echo hi", job_name="tst", time="00:10:00", partition="debug"
    )
    assert "#SBATCH --job-name=tst" in script
    assert "#SBATCH --time=00:10:00" in script
    assert "#SBATCH --partition=debug" in script
    assert "echo hi" in script


@pytest.mark.parametrize("cmd", ["echo hi && rm -rf /", "echo hi; rm -rf /", "bad\ncmd"])
def test_generate_slurm_script_rejects_bad(cmd: str) -> None:
    with pytest.raises(ValueError):
        generate_slurm_script(cmd)


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
