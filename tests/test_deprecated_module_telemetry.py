from __future__ import annotations

import importlib
import sys
import warnings
from pathlib import Path

from genecoder.metrics import get_metrics, set_metrics_path


MODULES_UNDER_TEST = [
    "genecoder.api",
    "genecoder.pipeline",
    "genecoder.compat.channel_cli",
    "genecoder.compat.channel_sim",
    "genecoder.compat.error_simulation",
]


def test_deprecated_modules_emit_usage_telemetry(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.json"
    set_metrics_path(metrics_path)
    try:
        for module_name in MODULES_UNDER_TEST:
            importlib.invalidate_caches()
            sys.modules.pop(module_name, None)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                importlib.import_module(module_name)

        metrics = get_metrics()
    finally:
        set_metrics_path(None)

    assert metrics["deprecated.module.total.imports"] >= len(MODULES_UNDER_TEST)
    for module_name in MODULES_UNDER_TEST:
        key = f"deprecated.module.{module_name.replace('_', '-')}.imports"
        assert metrics[key] >= 1
