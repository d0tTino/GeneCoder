from tests.test_cli import run_cli_command


def test_cli_profiles_lists() -> None:
    result = run_cli_command(["channel", "list-profiles"])
    assert result.returncode == 0
    out = result.stdout
    assert "Illumina" in out
    assert "Nanopore" in out
    assert "miseq" in out
    assert "minion" in out
    assert "novaseq" in out
    assert "r10" in out
    assert "r9" in out
    assert "r10.3" in out
    assert "r10.4" in out
