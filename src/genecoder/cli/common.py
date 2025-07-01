"""Helper utilities shared across CLI modules."""

from __future__ import annotations

import argparse
import concurrent.futures
import logging
import os
from typing import Callable, Sequence, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


def run_tasks(
    tasks: Sequence[tuple[str, str, argparse.Namespace]],
    worker: Callable[[str, str, argparse.Namespace], T],
    *,
    description: str,
    collect_results: bool = False,
) -> list[T]:
    """Execute tasks concurrently when there are multiple inputs."""

    results: list[T] = []
    num_tasks = len(tasks)
    if num_tasks > 1:
        logger.info(
            "Starting batch %s for %d files using ThreadPoolExecutor...",
            description,
            num_tasks,
        )
        cpu_count = os.cpu_count() or 1
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(8, cpu_count + 4)
        ) as executor:
            future_to_task = {
                executor.submit(worker, t[0], t[1], t[2]): t for t in tasks
            }
            for future in concurrent.futures.as_completed(future_to_task):
                try:
                    res = future.result()
                    if collect_results:
                        results.append(res)
                except Exception:
                    logger.exception(
                        "A file %s task generated an exception", description
                    )
        logger.info("\nBatch %s finished.", description)
    else:
        if tasks:
            res = worker(tasks[0][0], tasks[0][1], tasks[0][2])
            if collect_results:
                results.append(res)
    return results
