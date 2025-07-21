import argparse
import logging
import sys

from genecoder import __version__
from genecoder.plugin_manager import init_plugins
# simulators are imported lazily by subcommands that need them

from typing import Any

# Delay heavy imports until building the parser to keep --version lightweight
encode: Any | None = None
decode: Any | None = None
analyze: Any | None = None
report: Any | None = None
channel: Any | None = None
bundle: Any | None = None
plugin: Any | None = None
benchmark: Any | None = None
cloud: Any | None = None
decode_ai: Any | None = None
stats: Any | None = None
data: Any | None = None
dashboard: Any | None = None


logger = logging.getLogger(__name__)


class _LessThanFilter(logging.Filter):
    def __init__(self, exclusive_maximum: int) -> None:
        super().__init__()
        self.max = exclusive_maximum

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - trivial
        return record.levelno < self.max


def setup_logging(level: int) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    fmt = logging.Formatter("%(message)s")

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(_LessThanFilter(logging.WARNING))
    stdout_handler.setFormatter(fmt)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(fmt)

    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(stderr_handler)


def build_parser() -> argparse.ArgumentParser:
    from . import (
        encode as _encode,
        decode as _decode,
        analyze as _analyze,
        report as _report,
        channel as _channel,
        bundle as _bundle,
        cloud as _cloud,
        decode_ai as _decode_ai,
        plugin as _plugin_mod,
        benchmark as _benchmark,
        stats as _stats,
        data as _data,
        dashboard as _dashboard,
    )

    global encode, decode, analyze, report, channel, bundle, cloud, plugin, benchmark, decode_ai, stats, data, dashboard

    encode = _encode
    decode = _decode
    analyze = _analyze
    report = _report
    channel = _channel
    bundle = _bundle
    cloud = _cloud
    decode_ai = _decode_ai
    plugin = _plugin_mod
    benchmark = _benchmark
    stats = _stats
    data = _data
    dashboard = _dashboard


    # Load plugins here so that dynamically registered codecs, FEC backends and
    # simulators are available during subcommand registration.
    init_plugins()

    parser = argparse.ArgumentParser(
        description=(
            "GeneCoder: Encode and decode data into simulated DNA sequences. "
            "For educational simulations only; see the README's Disclaimer. "
            "For a quick demo see docs/vertical_slice.md."
        ),
        usage="%(prog)s [-h] [--version] [-v] [-q] COMMAND ...",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, width=79),
    )
    parser.add_argument("--version", action="version", version=f"GeneCoder {__version__}")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase output verbosity (can be used multiple times).")
    parser.add_argument("-q", "--quiet", action="count", default=0, help="Decrease output verbosity (can be used multiple times).")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    encode.register_subcommand(subparsers)
    decode.register_subcommand(subparsers)
    decode_ai.register_subcommand(subparsers)
    analyze.register_subcommand(subparsers)
    report.register_subcommand(subparsers)
    channel.register_subcommand(subparsers)
    bundle.register_subcommand(subparsers)
    cloud.register_subcommand(subparsers)
    plugin.register_subcommand(subparsers)
    benchmark.register_subcommand(subparsers)
    stats.register_subcommand(subparsers)
    data.register_subcommand(subparsers)
    dashboard.register_subcommand(subparsers)

    return parser




def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.INFO - (args.verbose * 10) + (args.quiet * 10)
    level = max(logging.DEBUG, min(logging.CRITICAL, level))
    setup_logging(level)

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
