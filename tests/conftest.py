import os
import sys
import types

# Ensure the ``src`` directory is importable
ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

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
