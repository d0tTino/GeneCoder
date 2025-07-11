from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ChannelConfig"]


@dataclass
class ChannelConfig:
    """Configuration options for :class:`~genecoder.simulators.pipeline.ChannelPipeline`."""

    parallel: bool = False
    workers: int | None = None
    use_process_pool: bool = False
    use_mpi: bool = False
