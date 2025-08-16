"""Utility functions for external simulators."""

from __future__ import annotations

import logging
import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence

from .formats import from_fasta, to_fasta
from .random_utils import make_rng
from .error_simulation import simulate_errors
from .utils import get_temp_dir

logger = logging.getLogger(__name__)


def _parse_env_options(command: str) -> list[str]:
    """Return additional options for ``command`` parsed from the environment.

    The environment variable ``GENECODER_<CMD>_OPTIONS`` allows forwarding extra
    command line arguments to the external simulators.  For security reasons
    only a limited set of characters is permitted.  If ``raw`` contains
    potentially dangerous characters a ``ValueError`` is raised.
    """

    env_var = f"GENECODER_{command.upper()}_OPTIONS"
    raw = os.getenv(env_var)
    if not raw:
        return []

    import re

    # Reject characters outside a conservative whitelist to avoid
    # command injection via shell metacharacters.
    if not raw.isprintable() or not re.fullmatch(r"[A-Za-z0-9_\-./=:'\"\s]*", raw):
        raise ValueError(f"Unsafe characters in {env_var}")

    import shlex

    try:
        options = shlex.split(raw)
    except ValueError as exc:  # pragma: no cover - error path
        logger.warning("Invalid %s value: %s", env_var, exc)
        return []

    flag_re = re.compile(r"^-{1,2}[A-Za-z0-9][A-Za-z0-9_-]*(=.+)?$")
    arg_re = re.compile(r"^[A-Za-z0-9./:_-]+$")

    for opt in options:
        if opt.startswith("-"):
            if not flag_re.fullmatch(opt):
                raise ValueError(f"Invalid option {opt!r} in {env_var}")
        else:
            if not arg_re.fullmatch(opt):
                raise ValueError(f"Invalid argument {opt!r} in {env_var}")

    logger.debug("Using %s=%r", env_var, options)
    return options


def _run_external(command: Sequence[str] | str, sequence: str) -> str:
    """Run an external simulator command on ``sequence``.

    The command must accept an input FASTA file and output FASTA to a
    second file: ``command <in> <out>``.
    """

    with tempfile.TemporaryDirectory(dir=get_temp_dir()) as tmpdir:
        input_path = Path(tmpdir) / "input.fasta"
        output_path = Path(tmpdir) / "output.fasta"
        input_path.write_text(to_fasta(sequence, "seq"))
        cmd_list = [command] if isinstance(command, str) else list(command)
        full_cmd = cmd_list + [str(input_path), str(output_path)]
        logger.debug("Running external command: %s", " ".join(full_cmd))
        try:
            subprocess.run(full_cmd, check=True)
        except subprocess.CalledProcessError as exc:  # pragma: no cover - error path
            raise RuntimeError(
                f"{cmd_list[0]} failed with exit code {exc.returncode}"
            ) from exc
        records = from_fasta(output_path.read_text())
        if not records:
            raise RuntimeError(f"{cmd_list[0]} produced no FASTA output")
        return records[0][1]


def _simulate_adapter(
    command: str,
    sequence: str,
    error_rate: float,
    rng: random.Random | None,
    extra_args: Sequence[str] | None = None,
) -> str:
    """Return ``sequence`` processed by an external ``command`` if available."""

    if shutil.which(command):
        try:
            cmd_list = [command, "-e", str(error_rate)]
            if extra_args:
                cmd_list += list(extra_args)
            cmd_list += _parse_env_options(command)
            return _run_external(cmd_list, sequence)
        except (ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
            logger.warning(
                "%s failed: %s; falling back to simple error model", command, exc
            )
    else:
        logger.warning(
            "%s not found; falling back to simple error model", command
        )

    if rng is None:
        rng = make_rng()
    return simulate_errors(sequence, error_rate, rng=rng)

