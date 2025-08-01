from tests.test_cli import run_cli_command


def test_pipeline_profiles_listed() -> None:
    result = run_cli_command(["pipeline", "--help"])
    assert result.returncode == 0
    out = result.stdout
    assert "miseq" in out
    assert "hiseq" in out
    assert "minion" in out
    assert "promethion" in out
    assert "novaseq" in out
    assert "r10" in out
