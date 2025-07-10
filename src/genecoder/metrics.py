import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "Metrics",
    "metrics",
    "increment",
    "get_metrics",
    "oligos_per_week",
]


def _get_metrics_path() -> Path:
    env = os.getenv("GENECODER_METRICS_PATH")
    if env:
        return Path(env)
    return Path.home() / ".genecoder" / "metrics.json"


def _load(path: Path) -> dict[str, object]:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _save(path: Path, metrics: dict[str, object]) -> None:
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
            if key == "oligos_simulated":
                ts_list = metrics.get("oligos_simulated_ts", [])
                if not isinstance(ts_list, list):
                    ts_list = []
                ts_list.append(datetime.now(timezone.utc).isoformat())
                metrics["oligos_simulated_ts"] = ts_list
            _save(self.path, metrics)

    def get_metrics(self) -> dict[str, object]:
        with self._lock:
            return _load(self.path)

    def oligos_per_week(self) -> dict[str, int]:
        with self._lock:
            data = _load(self.path)
            ts_list = data.get("oligos_simulated_ts", [])
        counts: dict[str, int] = {}
        for ts in ts_list:
            try:
                dt = datetime.fromisoformat(ts)
            except Exception:
                continue
            iso_year, iso_week, _ = dt.isocalendar()
            key = f"{iso_year}-W{iso_week:02d}"
            counts[key] = counts.get(key, 0) + 1
        return counts


metrics = Metrics()


def increment(key: str) -> None:
    metrics.increment(key)


def get_metrics() -> dict[str, object]:
    return metrics.get_metrics()


def oligos_per_week() -> dict[str, int]:
    return metrics.oligos_per_week()


