from tests.test_cli import run_cli_command


def test_help_shows_disclaimer():
    result = run_cli_command(["--help"])
    assert result.returncode == 0
    assert "readme" in result.stdout.lower()


def test_capabilities_cli_hides_async_lines_in_local_only_mode(monkeypatch):
    monkeypatch.setenv("GENECODER_EXECUTION_MODE", "local-only")
    monkeypatch.delenv("GENECODER_QUEUE_BACKEND", raising=False)
    monkeypatch.delenv("GENECODER_REMOTE_WORKER", raising=False)
    result = run_cli_command(["capabilities"])
    assert result.returncode == 0
    assert "execution_mode: local-only" in result.stdout
    assert "queue_backend: none" in result.stdout
    assert "async_job_mode" not in result.stdout
    assert "remote_worker" not in result.stdout
