import json
import os
import subprocess
import sys

from tests.conftest import PROJECT_ROOT


def _run_fec_bench(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    src_path = PROJECT_ROOT / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [sys.executable, str(PROJECT_ROOT / "benchmarks" / "fec_bench.py")] + args
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=PROJECT_ROOT)


def test_fec_bench_json() -> None:
    result = _run_fec_bench(["--size", "16", "--error-prob", "0", "--format", "json"])
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert all("fec" in item for item in data)


def test_fec_bench_csv() -> None:
    result = _run_fec_bench(["--size", "16", "--error-prob", "0", "--format", "csv"])
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.strip().splitlines() if line]
    assert lines[0].startswith("fec,")
    assert len(lines) >= 2
