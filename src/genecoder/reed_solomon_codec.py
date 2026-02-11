"""Reed--Solomon encoding and decoding utilities using ``reedsolo``.

This module provides minimal wrappers around the :mod:`reedsolo` library to
encode and decode byte strings with Reed--Solomon error correction. The number
of parity symbols (``nsym``), symbol size (``c_exp``) and primitive polynomial
can be specified when constructing the codec.
"""

# ruff: noqa: ANN401

# ruff: noqa: ANN401

from __future__ import annotations

from typing import Tuple, TYPE_CHECKING, Mapping, Any

from .plugin_api import FEC


_HAS_REEDSOLO: bool = False

if TYPE_CHECKING:
    from reedsolo import RSCodec, ReedSolomonError
else:
    try:  # pragma: no cover - optional dependency
        from reedsolo import RSCodec, ReedSolomonError
        _HAS_REEDSOLO = True
    except ImportError:  # pragma: no cover - missing optional dependency
        RSCodec = None

        class ReedSolomonError(Exception):
            """Placeholder used when :mod:`reedsolo` is unavailable."""

        _HAS_REEDSOLO = False


def _require_reedsolo() -> None:  # pragma: no cover - helper
    """Ensure the :mod:`reedsolo` package is installed."""
    if not _HAS_REEDSOLO:
        raise ImportError(
            "reedsolo is required for Reed-Solomon encoding. Install it via 'pip install reedsolo'."
        )


def encode_data_rs(
    data: bytes,
    nsym: int = 10,
    *,
    symbol_size: int | None = None,
    primitive: int | None = None,
) -> Tuple[bytes, int, int | None, int | None]:
    """Encode ``data`` with Reed--Solomon FEC.

    Parameters
    ----------
    data:
        Byte string to encode.
    nsym:
        Number of parity symbols to append. Defaults to ``10``.
    symbol_size:
        Optional symbol size (``c_exp``) in bits.
    primitive:
        Optional primitive polynomial value.

    Returns
    -------
    tuple
        ``(encoded_bytes, nsym, symbol_size, primitive)`` where ``encoded_bytes``
        is the encoded output including parity symbols.
    """
    _require_reedsolo()
    rs_kwargs: dict[str, int] = {}
    if symbol_size is not None:
        rs_kwargs["c_exp"] = symbol_size
    if primitive is not None:
        rs_kwargs["prim"] = primitive
    rs = RSCodec(nsym, **rs_kwargs)
    encoded = rs.encode(data)
    used_symbol_size = rs_kwargs.get("c_exp", getattr(rs, "c_exp", None))
    used_primitive = rs_kwargs.get("prim", getattr(rs, "prim", None))
    return bytes(encoded), nsym, used_symbol_size, used_primitive


def decode_data_rs(
    encoded: bytes,
    nsym: int,
    *,
    symbol_size: int | None = None,
    primitive: int | None = None,
) -> Tuple[bytes, int]:
    """Decode Reed--Solomon encoded ``encoded`` bytes.

    Parameters
    ----------
    encoded:
        Encoded data including parity symbols.
    nsym:
        Number of parity symbols that were used during encoding.
    symbol_size:
        Optional symbol size (``c_exp``) in bits.
    primitive:
        Optional primitive polynomial value used during encoding.

    Returns
    -------
    tuple
        ``(decoded_bytes, corrections)`` where ``corrections`` is the number of
        symbols corrected during decoding.

    Raises
    ------
    ValueError
        If decoding fails due to too many errors.
    """
    _require_reedsolo()
    rs_kwargs: dict[str, int] = {}
    if symbol_size is not None:
        rs_kwargs["c_exp"] = symbol_size
    if primitive is not None:
        rs_kwargs["prim"] = primitive
    rs = RSCodec(nsym, **rs_kwargs)
    try:
        decoded, _full, err_pos = rs.decode(encoded)
    except ReedSolomonError as exc:  # pragma: no cover - error path
        raise ValueError(f"Reed-Solomon decode failed: {exc}") from exc
    return bytes(decoded), len(err_pos)


class ReedSolomonFEC(FEC):
    """Reed--Solomon FEC backend implementing :class:`BaseFEC`."""

    def encode(
        self,
        data: bytes,
        /,
        *,
        nsym: int = 10,
        symbol_size: int | None = None,
        primitive: int | None = None,
        **kwargs: Any,
    ) -> Tuple[bytes, Mapping[str, Any]]:  # noqa: ANN401
        encoded, used_nsym, used_symbol_size, used_primitive = encode_data_rs(
            data,
            nsym,
            symbol_size=symbol_size,
            primitive=primitive,
        )
        info: dict[str, Any] = {"nsym": used_nsym}
        if used_symbol_size is not None:
            info["symbol_size"] = used_symbol_size
        if used_primitive is not None:
            info["primitive"] = used_primitive
        return encoded, info

    def decode(
        self,
        encoded: bytes,
        info: Mapping[str, Any],
        /,
        **kwargs: Any,
    ) -> Tuple[bytes, int]:  # noqa: ANN401
        symbol_size_val = info.get("symbol_size")
        primitive_val = info.get("primitive")
        return decode_data_rs(
            encoded,
            int(info["nsym"]),
            symbol_size=int(symbol_size_val) if symbol_size_val is not None else None,
            primitive=int(primitive_val) if primitive_val is not None else None,
        )


from typing import Callable

def register(register_fec: Callable[[str, type[FEC]], None]) -> None:
    """Register this module's FEC backend."""
    register_fec("reed_solomon", ReedSolomonFEC)

