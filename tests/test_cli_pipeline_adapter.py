from __future__ import annotations

import argparse
from pathlib import Path

from genecoder.cli import pipeline as pipeline_cli


def test_pipeline_cli_uses_ui_service_contract(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "input.bin"
    source.write_bytes(b"adapter")

    class StubResponse:
        decoded = b"adapter"
        run_schema = {"schema_version": "1.1", "outcome": {"metrics": {}}, "dashboard_metrics": {}}

    called = {"count": 0}

    class StubService:
        def run_pipeline(self, request):  # noqa: ANN001
            called["count"] += 1
            metrics_path = Path(str(request.output_path) + ".json")
            metrics_path.write_text("{}", encoding="utf-8")
            metrics_path.with_suffix(".manifest.json").write_text("{}", encoding="utf-8")
            return StubResponse()

    monkeypatch.setattr(pipeline_cli, "UIService", StubService)

    args = argparse.Namespace(
        seed=None,
        metrics_path=None,
        launch_dashboard=False,
        config=None,
        codec="reverse",
        fec=None,
        channel="none",
        sub_rate=None,
        ins_rate=None,
        del_rate=None,
        explain_coding_stack=False,
        mpi_workers=None,
        input=str(source),
        output=str(tmp_path / "decoded.bin"),
        emit_manifest_report=False,
    )

    pipeline_cli._handle_command(args)

    assert called["count"] == 1
