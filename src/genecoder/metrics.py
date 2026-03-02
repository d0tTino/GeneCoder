import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, IO, cast
from os import PathLike

try:  # pragma: no cover - optional dependency
    import portalocker
except Exception:  # pragma: no cover - fallback for tests
    import types

    class _NoLock:
        def __init__(self, path: str | os.PathLike[str], mode: str = "r", *, timeout: int | None = None, encoding: str | None = None) -> None:  # noqa: D401,E501
            """Simplified lock that just opens ``path`` without locking."""
            self.path = path
            self.mode = mode
            self.encoding = encoding
            self.fh: IO[str] | None = None

        def __enter__(self) -> IO[str]:
            self.fh = open(self.path, self.mode, encoding=self.encoding)
            return self.fh

        def __exit__(self, exc_type: type | None, exc: BaseException | None, tb: object | None) -> None:
            if self.fh:
                self.fh.close()

    portalocker = cast(Any, types.SimpleNamespace(Lock=_NoLock))

__all__ = ["Metrics", "metrics", "increment", "get_metrics", "oligos_per_week", "set_metrics_path"]


def _get_metrics_path() -> Path:
    env = os.getenv("GENECODER_METRICS_PATH")
    if env:
        return Path(env)
    return Path.home() / ".genecoder" / "metrics.json"


def _load(path: Path, fh: IO[str] | None = None) -> dict[str, object]:
    if fh is not None:
        fh.seek(0)
        content = fh.read()
        if content:
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {}
    if path.is_file():
        try:
            with portalocker.Lock(path, "r", timeout=10, encoding="utf-8") as f:
                return _load(path, f)
        except Exception:
            pass
    return {}


def _save(path: Path, metrics: dict[str, object], fh: IO[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(metrics)

    def _write(handle: IO[str]) -> None:
        handle.seek(0)
        handle.truncate(0)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())

    if fh is not None:
        _write(fh)
    else:
        with portalocker.Lock(path, "a+", timeout=10, encoding="utf-8") as f:
            _write(f)


class Metrics:
    """Operational telemetry manager for usage counters and heartbeat timestamps."""

    def __init__(self, path: Path | str | PathLike[str] | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path or _get_metrics_path()

    def set_path(self, path: Path | str | PathLike[str] | None) -> None:
        with self._lock:
            self._path = Path(path) if path is not None else None

    def increment(self, key: str) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with portalocker.Lock(self.path, "a+", timeout=10, encoding="utf-8") as fh:
                metrics = _load(self.path, fh)
                current = metrics.get(key, 0)
                if not isinstance(current, int):
                    current = 0
                metrics[key] = current + 1

                if key in {"oligos_simulated", "heartbeat"}:
                    ts_obj: Any = metrics.get(f"{key}_ts", [])
                    ts_list = ts_obj if isinstance(ts_obj, list) else []
                    ts_list.append(datetime.now(timezone.utc).isoformat())
                    metrics[f"{key}_ts"] = ts_list
                _save(self.path, metrics, fh)

    def get_metrics(self) -> dict[str, object]:
        with self._lock:
            if self.path.is_file():
                with portalocker.Lock(self.path, "r", timeout=10, encoding="utf-8") as fh:
                    return _load(self.path, fh)
            return {}

    def oligos_per_week(self) -> dict[str, int]:
        with self._lock:
            with portalocker.Lock(self.path, "r", timeout=10, encoding="utf-8") as fh:
                data = _load(self.path, fh)
                ts_list = data.get("oligos_simulated_ts", [])
                if not isinstance(ts_list, list):
                    ts_list = []

        counts: dict[str, int] = {}
        for ts in ts_list:
            try:
                dt = datetime.fromisoformat(ts)
            except Exception:
                continue
            iso_year, iso_week, _ = dt.isocalendar()
            wk = f"{iso_year}-W{iso_week:02d}"
            counts[wk] = counts.get(wk, 0) + 1
        return counts


metrics = Metrics()


def increment(key: str) -> None:
    metrics.increment(key)


def get_metrics() -> dict[str, object]:
    return metrics.get_metrics()


def oligos_per_week() -> dict[str, int]:
    return metrics.oligos_per_week()


def set_metrics_path(path: Path | str | PathLike[str] | None) -> None:
    metrics.set_path(path)
