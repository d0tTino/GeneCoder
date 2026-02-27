from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import random
from typing import Literal

logger = logging.getLogger(__name__)


StageName = Literal["global", "encode", "simulate", "decode"]
_STAGE_OFFSETS: dict[StageName, int] = {
    "global": 0,
    "encode": 1,
    "simulate": 2,
    "decode": 3,
}


@dataclass(frozen=True)
class RunContext:
    """Immutable runtime randomness context for deterministic pipeline runs."""

    global_seed: int | None
    encode_seed: int | None
    simulate_seed: int | None
    decode_seed: int | None
    global_rng: random.Random
    encode_rng: random.Random
    simulate_rng: random.Random
    decode_rng: random.Random
    seed_source: str

    def seed_for_stage(self, stage: StageName) -> int | None:
        if stage == "global":
            return self.global_seed
        if stage == "encode":
            return self.encode_seed
        if stage == "simulate":
            return self.simulate_seed
        return self.decode_seed

    def rng_for_stage(self, stage: StageName) -> random.Random:
        if stage == "global":
            return self.global_rng
        if stage == "encode":
            return self.encode_rng
        if stage == "simulate":
            return self.simulate_rng
        return self.decode_rng

    def seed_provenance(self) -> dict[str, object]:
        return {
            "source": self.seed_source,
            "global_seed": self.global_seed,
            "stage_seeds": {
                "encode": self.encode_seed,
                "simulate": self.simulate_seed,
                "decode": self.decode_seed,
            },
        }


def _parse_seed(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _derive_stage_seed(global_seed: int | None, stage: StageName, explicit: int | None) -> int | None:
    if explicit is not None:
        return explicit
    if global_seed is None:
        return None
    return global_seed + _STAGE_OFFSETS[stage]


def make_run_context(
    *,
    global_seed: int | None = None,
    encode_seed: int | None = None,
    simulate_seed: int | None = None,
    decode_seed: int | None = None,
) -> RunContext:
    """Build a :class:`RunContext` with CLI-first and env-fallback precedence.

    Precedence rules:
    1) Explicit function arguments always win.
    2) If no explicit seeds are supplied, fallback to ``GENECODER_SIM_SEED``.
    """

    explicit_any = any(
        value is not None for value in (global_seed, encode_seed, simulate_seed, decode_seed)
    )

    source = "explicit"
    if not explicit_any:
        env_seed_raw = os.getenv("GENECODER_SIM_SEED")
        env_seed = _parse_seed(env_seed_raw)
        if env_seed_raw is not None and env_seed is None:
            logger.warning("Invalid GENECODER_SIM_SEED %r ignored", env_seed_raw)
        if env_seed is not None:
            logger.warning(
                "Using GENECODER_SIM_SEED environment fallback; prefer CLI/API run context inputs."
            )
            global_seed = env_seed
            source = "env_fallback"
        else:
            source = "default_rng"

    encode_seed = _derive_stage_seed(global_seed, "encode", _parse_seed(encode_seed))
    simulate_seed = _derive_stage_seed(global_seed, "simulate", _parse_seed(simulate_seed))
    decode_seed = _derive_stage_seed(global_seed, "decode", _parse_seed(decode_seed))

    return RunContext(
        global_seed=_parse_seed(global_seed),
        encode_seed=encode_seed,
        simulate_seed=simulate_seed,
        decode_seed=decode_seed,
        global_rng=random.Random(_parse_seed(global_seed)),
        encode_rng=random.Random(encode_seed),
        simulate_rng=random.Random(simulate_seed),
        decode_rng=random.Random(decode_seed),
        seed_source=source,
    )
