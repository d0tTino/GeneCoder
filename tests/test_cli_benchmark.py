import json
from tests.test_cli import run_cli_command


def test_cli_benchmark_fec_json() -> None:
    result = run_cli_command([
        "benchmark",
        "fec",
        "--size",
        "16",
        "--error-prob",
        "0",
        "--format",
        "json",
    ])
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert all("fec" in item for item in data)


def test_cli_benchmark_fec_csv() -> None:
    result = run_cli_command([
        "benchmark",
        "fec",
        "--size",
        "16",
        "--error-prob",
        "0",
        "--format",
        "csv",
    ])
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line]
    assert lines[0].startswith("fec,")
    assert len(lines) >= 2
