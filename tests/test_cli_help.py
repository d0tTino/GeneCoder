from tests.test_cli import run_cli_command


def test_help_shows_disclaimer():
    result = run_cli_command(["--help"])
    assert result.returncode == 0
    assert "readme" in result.stdout.lower()
