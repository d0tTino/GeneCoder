import json
import os
import sys
import types
from typing import Mapping, Sequence

import pytest

# Ensure the ``src`` directory is importable
ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

os.environ.setdefault("SKIP_PACKAGING_TESTS", "1")

# Provide minimal cryptography exceptions only if the real dependency is missing
try:  # pragma: no cover - exercised only when cryptography is absent
    import cryptography  # noqa: F401
    import cryptography.exceptions  # noqa: F401
except Exception:  # pragma: no cover - import guard
    crypto_mod = types.ModuleType("cryptography")
    crypto_exc = types.ModuleType("cryptography.exceptions")

    class InvalidSignature(Exception):
        pass

    class UnsupportedAlgorithm(Exception):
        pass

    crypto_exc.InvalidSignature = InvalidSignature
    crypto_exc.UnsupportedAlgorithm = UnsupportedAlgorithm
    crypto_mod.exceptions = crypto_exc
    sys.modules.setdefault("cryptography", crypto_mod)
    sys.modules.setdefault("cryptography.exceptions", crypto_exc)

# Minimal stubs for fastapi-limiter so imports succeed when dependency is missing
try:  # pragma: no cover - exercised only when fastapi-limiter is absent
    import fastapi_limiter  # noqa: F401
    import fastapi_limiter.depends  # noqa: F401
except Exception:  # pragma: no cover - import guard
    limiter = types.ModuleType("fastapi_limiter")
    limiter.FastAPILimiter = types.SimpleNamespace(init=lambda *_a, **_k: None)

    depends = types.ModuleType("fastapi_limiter.depends")
    depends.RateLimiter = lambda *_a, **_k: (lambda func: func)

    sys.modules.setdefault("fastapi_limiter", limiter)
    sys.modules.setdefault("fastapi_limiter.depends", depends)

# Only stub YAML when the library is unavailable
try:  # pragma: no cover - exercised only when PyYAML is absent
    import yaml  # noqa: F401
except Exception:  # pragma: no cover - import guard
    yaml_stub = types.ModuleType("yaml")

    def _safe_load(_data):
        return {}

    def _safe_dump(_data, **_k):
        return ""

    class YAMLError(Exception):
        pass

    yaml_stub.safe_load = _safe_load
    yaml_stub.safe_dump = _safe_dump
    yaml_stub.YAMLError = YAMLError
    sys.modules.setdefault("yaml", yaml_stub)


@pytest.fixture
def mock_coverage_distribution(monkeypatch: pytest.MonkeyPatch) -> dict[int, float]:
    """Provide a deterministic coverage distribution for simulator tests."""

    def _fake_loader(value: object) -> dict[int, float]:
        if value in (None, "", {}, []):
            return {4: 1.0}
        if isinstance(value, Mapping):
            result = {int(k): float(v) for k, v in value.items()}
            return result or {4: 1.0}
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            result: dict[int, float] = {}
            for item in value:
                try:
                    cov = int(item)
                except (TypeError, ValueError):
                    continue
                result[cov] = result.get(cov, 0.0) + 1.0
            return result or {4: 1.0}
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {4: 1.0}
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed_map: dict[int, float] = {}
                for chunk in raw.split(","):
                    chunk = chunk.strip()
                    if not chunk:
                        continue
                    if ":" in chunk:
                        key, weight = chunk.split(":", 1)
                    else:
                        key, weight = chunk, "1"
                    try:
                        cov = int(key.strip())
                        wt = float(weight.strip())
                    except ValueError:
                        continue
                    parsed_map[cov] = parsed_map.get(cov, 0.0) + wt
                parsed = parsed_map
            if isinstance(parsed, Mapping):
                result = {int(k): float(v) for k, v in parsed.items()}
                return result or {4: 1.0}
            if isinstance(parsed, Sequence):
                result: dict[int, float] = {}
                for item in parsed:
                    try:
                        cov = int(item)
                    except (TypeError, ValueError):
                        continue
                    result[cov] = result.get(cov, 0.0) + 1.0
                return result or {4: 1.0}
            return {4: 1.0}
        try:
            cov_value = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return {4: 1.0}
        return {cov_value: 1.0}

    monkeypatch.setattr("genecoder.simulators.batch_utils.load_coverage_distribution", _fake_loader)
    monkeypatch.setattr("genecoder.simulators.illumina.load_coverage_distribution", _fake_loader)
    monkeypatch.setattr("genecoder.simulators.nanopore.load_coverage_distribution", _fake_loader)
    return _fake_loader(None)
