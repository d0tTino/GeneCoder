import json
import os
from pathlib import Path

__all__ = ["increment", "get_metrics"]


def _get_metrics_path() -> Path:
    env = os.getenv("GENECODER_METRICS_PATH")
    if env:
        return Path(env)
    return Path.home() / ".genecoder" / "metrics.json"


def _load() -> dict[str, int]:
    path = _get_metrics_path()
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {k: int(v) for k, v in data.items()}
        except Exception:
            pass
    return {}


def _save(metrics: dict[str, int]) -> None:
    path = _get_metrics_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics), encoding="utf-8")


def increment(key: str) -> None:
    metrics = _load()
    metrics[key] = metrics.get(key, 0) + 1
    _save(metrics)


def get_metrics() -> dict[str, int]:
    return _load()
