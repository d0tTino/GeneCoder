import json
import os
import threading
from pathlib import Path

__all__ = ["Metrics", "metrics", "increment", "get_metrics"]


def _get_metrics_path() -> Path:
    env = os.getenv("GENECODER_METRICS_PATH")
    if env:
        return Path(env)
    return Path.home() / ".genecoder" / "metrics.json"


def _load(path: Path) -> dict[str, int]:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {k: int(v) for k, v in data.items()}
        except Exception:
            pass
    return {}


def _save(path: Path, metrics: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(metrics), encoding="utf-8")
    os.replace(tmp, path)


class Metrics:
    """Simple metrics manager for atomic updates."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        """Metrics file path, respecting environment overrides."""
        return self._path or _get_metrics_path()

    def increment(self, key: str) -> None:
        with self._lock:
            metrics = _load(self.path)
            metrics[key] = metrics.get(key, 0) + 1
            _save(self.path, metrics)

    def get_metrics(self) -> dict[str, int]:
        with self._lock:
            return _load(self.path)


metrics = Metrics()


def increment(key: str) -> None:
    metrics.increment(key)


def get_metrics() -> dict[str, int]:
    return metrics.get_metrics()


