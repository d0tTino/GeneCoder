from __future__ import annotations

import json

import benchmarks.error_rate as error_rate
import benchmarks.throughput as throughput


def test_error_rate_main_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["error_rate.py", "--format", "json"])
    error_rate.main()
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["benchmark"] == "error_rate"
    assert payload["schema_version"] == "1.0.0"


def test_throughput_main_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["throughput.py", "--format", "json"])
    throughput.main()
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["benchmark"] == "throughput"
    assert payload["schema_version"] == "1.0.0"
