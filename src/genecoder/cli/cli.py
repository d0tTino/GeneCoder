import argparse
import logging
import sys

from genecoder import __version__
from genecoder.plugins import load_plugins, SIMULATOR_REGISTRY
from typing import Any

# Delay heavy imports until building the parser to keep --version lightweight
encode: Any | None = None
decode: Any | None = None
analyze: Any | None = None
report: Any | None = None

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
    from . import encode as _encode, decode as _decode, analyze as _analyze, report as _report

    global encode, decode, analyze, report
    encode = _encode
    decode = _decode
    analyze = _analyze
    report = _report

    # Load plugins here so that dynamically registered codecs, FEC backends and
    # simulators are available during subcommand registration.
    load_plugins()

    parser = argparse.ArgumentParser(
        description="GeneCoder: Encode and decode data into simulated DNA sequences."
    )
    parser.add_argument("--version", action="version", version=f"GeneCoder {__version__}")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase output verbosity (can be used multiple times).")
    parser.add_argument("-q", "--quiet", action="count", default=0, help="Decrease output verbosity (can be used multiple times).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    encode.register_subcommand(subparsers)
    decode.register_subcommand(subparsers)
    analyze.register_subcommand(subparsers)
    report.register_subcommand(subparsers)

    sim_parser = subparsers.add_parser(
        "simulate-errors", help="Introduce random errors into a FASTA sequence."
    )
    sim_parser.add_argument("--input-file", type=str, required=True, help="Path to the input FASTA file.")
    sim_parser.add_argument("--output-file", type=str, required=True, help="Path to save the corrupted FASTA file.")
    sim_parser.add_argument("--sub-prob", type=float, default=0.01, help="Substitution probability per nucleotide.")
    sim_parser.add_argument("--ins-prob", type=float, default=0.0, help="Insertion probability after each nucleotide.")
    sim_parser.add_argument("--del-prob", type=float, default=0.0, help="Deletion probability per nucleotide.")
    sim_choices = list(sorted(SIMULATOR_REGISTRY.keys())) or ["none"]
    sim_parser.add_argument(
        "--simulator",
        type=str,
        choices=sim_choices,
        help="Use a named simulator instead of simple probabilities.",
    )
    sim_parser.add_argument(
        "--read-length",
        type=int,
        help="Override read length when using a simulator.",
    )
    sim_parser.add_argument("--seed", type=int, default=None, help="Random seed for deterministic output.")
    sim_parser.set_defaults(func=_handle_sim_errors)

    return parser


def _handle_sim_errors(args: argparse.Namespace) -> None:
    from genecoder.formats import to_fasta, from_fasta
    from genecoder.error_simulation import introduce_errors
    from genecoder.simulators import SIMULATOR_REGISTRY
    import os
    import random

    try:
        with open(args.input_file, "r", encoding="utf-8") as f_in:
            fasta_str = f_in.read()
        records = from_fasta(fasta_str)
        if not records:
            logger.error(f"Error: No FASTA records found in {args.input_file}.")
            raise SystemExit(1)
        header, seq = records[0]
        rng = random.Random(args.seed)
        sim_name = getattr(args, "simulator", None)
        if sim_name:
            if sim_name not in SIMULATOR_REGISTRY:
                logger.error("Unknown simulator: %s", sim_name)
                raise SystemExit(1)
            channel = SIMULATOR_REGISTRY[sim_name]
            if hasattr(channel, "substitution_rate"):
                channel.substitution_rate = args.sub_prob
            if hasattr(channel, "insertion_rate"):
                channel.insertion_rate = args.ins_prob
            if hasattr(channel, "deletion_rate"):
                channel.deletion_rate = args.del_prob
            read_len = getattr(args, "read_length", None)
            if read_len is not None and hasattr(channel, "read_length"):
                channel.read_length = read_len
            corrupted = channel.simulate(seq)
        else:
            corrupted = introduce_errors(
                seq,
                substitution_prob=args.sub_prob,
                insertion_prob=args.ins_prob,
                deletion_prob=args.del_prob,
                rng=rng,
            )
        new_header = f"{header} sub_prob={args.sub_prob} ins_prob={args.ins_prob} del_prob={args.del_prob}"
        fasta_out = to_fasta(corrupted, new_header, line_width=80)
        os.makedirs(os.path.dirname(args.output_file) or ".", exist_ok=True)
        with open(args.output_file, "w", encoding="utf-8") as f_out:
            f_out.write(fasta_out)
        logger.info(f"Corrupted FASTA sequence written to {args.output_file}")
    except FileNotFoundError:
        logger.error(f"Error: Input file {args.input_file} not found.")
        raise SystemExit(1)
    except ValueError as exc:
        logger.error("Error during simulate-errors: %s", exc)
        raise SystemExit(1)


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
