#!/usr/bin/env python
"""Demonstrate running ChannelPipeline under MPI."""
from __future__ import annotations

from genecoder.channel_config import ChannelConfig
from genecoder.channel_sim import Channel
from genecoder.simulators.pipeline import ChannelPipeline

try:
    from mpi4py import MPI
except Exception as exc:  # pragma: no cover - optional dependency
    raise SystemExit("mpi4py is required to run this example") from exc


def main() -> None:
    """Run a simple pipeline with MPI and print the result."""
    rank = MPI.COMM_WORLD.Get_rank()
    pipeline = ChannelPipeline([Channel(0.1), Channel(0.2)])
    cfg = ChannelConfig(parallel=True, workers=2, use_mpi=True)
    result = pipeline.simulate("ACGTACGTACGT", config=cfg)
    print(f"Rank {rank} result: {result}")


if __name__ == "__main__":
    main()
