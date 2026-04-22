from __future__ import annotations

"""Compatibility facade for legacy coding stack compilation entrypoints."""

from collections.abc import Mapping
from typing import Any

from genecoder.coding.stack import compile_legacy_stack, compile_stack_from_config, plan_stack_from_config
from genecoder.constraints import ConstraintPolicy


def compile_legacy_coding_stack(
    codec: str,
    fec: str | None,
    *,
    constraint_policy: ConstraintPolicy | None = None,
):
    return compile_legacy_stack(codec, fec, constraint_policy=constraint_policy)


def compile_coding_stack_from_config(
    config: Mapping[str, Any],
    *,
    constraint_policy: ConstraintPolicy | None = None,
):
    return compile_stack_from_config(config, constraint_policy=constraint_policy)


def plan_coding_stack(config: Mapping[str, Any], *, constraint_policy: ConstraintPolicy | None = None):
    return plan_stack_from_config(config, constraint_policy=constraint_policy)


__all__ = [
    "compile_legacy_coding_stack",
    "compile_coding_stack_from_config",
    "plan_coding_stack",
]
