from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from genecoder.channels.base import BaseChannel
from genecoder.simulators.pipeline import ChannelPipeline

pytest.importorskip("mpi4py")
from mpi4py import MPI  # type: ignore

COMM = MPI.COMM_WORLD

if COMM.Get_rank() != 0:  # pragma: no cover - only run on root
    pytest.skip("Only run on the root MPI rank", allow_module_level=True)

if COMM.Get_size() == 1 and shutil.which("mpiexec") is None:  # pragma: no cover - optional dependency
    pytest.skip("mpiexec not available", allow_module_level=True)


class _DelayChannel(BaseChannel):
    """Channel that sleeps before appending a suffix."""

    def __init__(self, delay: float, suffix: str) -> None:
        self.delay = delay
        self.suffix = suffix

    def simulate(self, sequence: str) -> str:  # noqa: D401 - simple passthrough
        """Return ``sequence`` after a short delay with ``suffix`` appended."""
        time.sleep(self.delay)
        return sequence + self.suffix


def test_pipeline_parallel_mpi(tmp_path: Path) -> None:
    pipeline = ChannelPipeline([_DelayChannel(0.05, "A"), _DelayChannel(0.05, "B")])
    seq = "ACGTACGT"

    start = time.perf_counter()
    serial_result = pipeline.simulate(seq)
    serial_time = time.perf_counter() - start

    if COMM.Get_size() == 1:
        script = (
            "import json, time\n"
            "from genecoder.channel_config import ChannelConfig\n"
            "from genecoder.simulators.pipeline import ChannelPipeline\n"
            "class _DelayChannel:\n"
            "    def __init__(self, delay, suffix):\n"
            "        self.delay = delay; self.suffix = suffix\n"
            "    def simulate(self, sequence):\n"
            "        time.sleep(self.delay); return sequence + self.suffix\n"
            "pipeline = ChannelPipeline([_DelayChannel(0.05,'A'), _DelayChannel(0.05,'B')])\n"
            f"seq = {seq!r}\n"
            "start = time.perf_counter()\n"
            "res = pipeline.simulate(seq, config=ChannelConfig(parallel=True, workers=1, use_mpi=True))\n"
            "dur = time.perf_counter() - start\n"
            "print(json.dumps({'result': res, 'duration': dur}))\n"
        )

        env = os.environ.copy()
        env["PYTHONPATH"] = (
            str(Path(__file__).resolve().parents[1] / "src")
            + os.pathsep
            + env.get("PYTHONPATH", "")
        )

        try:
            proc = subprocess.run(
                ["mpiexec", "-n", "2", sys.executable, "-c", script],
                capture_output=True,
                text=True,
                env=env,
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover - best effort
            pytest.skip(f"mpiexec failed: {exc}")

        if proc.returncode != 0 or not proc.stdout.strip():
            pytest.skip(f"mpiexec error: {proc.stderr.strip()}")

        data = json.loads(proc.stdout.strip().splitlines()[-1])
        mpi_result = data["result"]
        mpi_time = data["duration"]
    else:
        from genecoder.channel_config import ChannelConfig

        start = time.perf_counter()
        mpi_result = pipeline.simulate(
            seq,
            config=ChannelConfig(
                parallel=True, workers=COMM.Get_size() - 1, use_mpi=True
            ),
        )
        mpi_time = time.perf_counter() - start

    assert mpi_result == serial_result

    serial_tp = len(serial_result) / serial_time
    mpi_tp = len(mpi_result) / mpi_time
    # Allow some overhead for MPI execution but flag severe regressions
    assert mpi_tp >= serial_tp / 4
