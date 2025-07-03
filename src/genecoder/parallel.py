from __future__ import annotations

"""Small helpers for running tasks in parallel."""

from typing import Callable, Iterable, TypeVar
import concurrent.futures
import os

__all__ = ["parallel_map"]

T = TypeVar("T")
R = TypeVar("R")


def parallel_map(
    func: Callable[[T], R],
    items: Iterable[T],
    *,
    workers: int | None = None,
    use_processes: bool = False,
) -> list[R]:
    """Apply ``func`` to ``items`` using threads or processes."""

    items = list(items)
    if not items:
        return []

    if workers is None:
        workers = min(len(items), os.cpu_count() or 1)

    executor_cls = (
        concurrent.futures.ProcessPoolExecutor
        if use_processes
        else concurrent.futures.ThreadPoolExecutor
    )
    with executor_cls(max_workers=workers) as executor:
        return list(executor.map(func, items))
