import importlib
import importlib.util
import sys
from typing import Any, Optional
import pytest


def _simulate_missing(module: str, missing: str, monkeypatch: pytest.MonkeyPatch) -> None:
    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, *args: Any, **kwargs: Any) -> Optional[object]:
        if name == missing:
            return None
        return real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    sys.modules.pop(module, None)
    with pytest.raises(pytest.skip.Exception):
        importlib.import_module(module)


def test_hypothesis_test_skips_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _simulate_missing("tests.test_error_simulation_hypothesis", "hypothesis", monkeypatch)


def test_numpy_test_skips_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _simulate_missing("tests.test_ldpc_fountain_extended", "numpy", monkeypatch)
