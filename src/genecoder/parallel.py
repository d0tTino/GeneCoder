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
    use_mpi: bool = False,
) -> list[R]:
    """Apply ``func`` to ``items`` using threads, processes or MPI."""

    items = list(items)
    if not items:
        return []

    if workers is None:
        workers = min(len(items), os.cpu_count() or 1)

    if use_mpi:
        try:  # pragma: no cover - optional dependency
            from mpi4py.futures import MPIPoolExecutor
        except Exception as exc:  # pragma: no cover - missing dependency
            raise RuntimeError("mpi4py is required for MPI execution") from exc
        executor_cls = MPIPoolExecutor
    else:
        executor_cls = (
            concurrent.futures.ProcessPoolExecutor
            if use_processes
            else concurrent.futures.ThreadPoolExecutor
        )
    with executor_cls(max_workers=workers) as executor:
        return list(executor.map(func, items))
