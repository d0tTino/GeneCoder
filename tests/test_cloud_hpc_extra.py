import pytest

pytest.importorskip("httpx")

from genecoder.cloud import CloudClient


def test_cloud_client_hpc_with_script(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {}

    def fake_generate(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("generate_slurm_script should not run")

    def fake_submit(script: str) -> str:
        called["script"] = script
        return "77"

    monkeypatch.setattr("genecoder.cloud.hpc.generate_slurm_script", fake_generate)
    monkeypatch.setattr("genecoder.cloud.hpc.submit_slurm_job", fake_submit)

    client = CloudClient("http://unused")
    jid = client.submit("hpc", {"script": "echo hi"})
    assert jid == "77"
    assert called["script"] == "echo hi"
