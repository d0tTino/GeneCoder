from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.harness import benchmark_payload, render_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reproducible throughput benchmarks")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()
    print(render_payload(benchmark_payload("throughput"), args.format))


if __name__ == "__main__":
    main()
