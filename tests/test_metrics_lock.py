import json
from multiprocessing import Process
from pathlib import Path

from genecoder.metrics import Metrics


def _worker(path: str) -> None:
    m = Metrics(Path(path))
    m.increment("concurrent")


def test_concurrent_increment(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.json"
    procs = [Process(target=_worker, args=(str(metrics_path),)) for _ in range(2)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

    data = json.loads(metrics_path.read_text())
    assert data["concurrent"] == 2
