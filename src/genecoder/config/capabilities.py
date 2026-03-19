from __future__ import annotations

"""Shared runtime capability manifest for API, CLI, and UI adapters."""

from dataclasses import asdict, dataclass
import os
from typing import Literal

ExecutionMode = Literal["local-only", "hybrid", "remote"]
QueueBackend = Literal["none", "redis", "custom"]


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RuntimeCapabilities:
    execution_mode: ExecutionMode = "local-only"
    queue_backend: QueueBackend = "none"
    remote_worker: bool = False

    @property
    def supports_async_jobs(self) -> bool:
        return self.queue_backend != "none"

    @property
    def local_only(self) -> bool:
        return self.execution_mode == "local-only" and not self.remote_worker

    @property
    def async_job_mode(self) -> str:
        return "queued" if self.supports_async_jobs else "local-inline"

    def to_manifest(self) -> dict[str, object]:
        data = asdict(self)
        data["supports_async_jobs"] = self.supports_async_jobs
        data["local_only"] = self.local_only
        data["async_job_mode"] = self.async_job_mode
        return data


def get_runtime_capabilities() -> RuntimeCapabilities:
    execution_mode = os.getenv("GENECODER_EXECUTION_MODE", "local-only").strip().lower() or "local-only"
    if execution_mode not in {"local-only", "hybrid", "remote"}:
        execution_mode = "local-only"

    queue_backend = os.getenv("GENECODER_QUEUE_BACKEND", "none").strip().lower() or "none"
    if queue_backend not in {"none", "redis", "custom"}:
        queue_backend = "custom"

    remote_worker = _get_bool("GENECODER_REMOTE_WORKER", default=False)
    if execution_mode == "local-only":
        queue_backend = "none"
        remote_worker = False

    return RuntimeCapabilities(
        execution_mode=execution_mode,
        queue_backend=queue_backend,
        remote_worker=remote_worker,
    )


def get_capability_manifest() -> dict[str, object]:
    return get_runtime_capabilities().to_manifest()
