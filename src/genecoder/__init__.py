"""Core modules for DNA encoding experiments."""

__version__ = "0.1.0"


_LAZY_ATTRS = {
    "EncodeOptions",
    "EncodeResult",
    "DecodeResult",
    "perform_encoding",
    "perform_decoding",
    "encrypt_data",
    "decrypt_data",
    "compute_checksum",
}

from .plugin_manager import (
    CODEC_REGISTRY,
    FEC_REGISTRY,
    init_plugins,
    load_plugins,
    install_registry_plugins,
)
from .simulators import SIMULATOR_REGISTRY, simulate_reads
from .channel_config import ChannelConfig
from .pipeline import SequencePipeline


__all__ = [
    *sorted(_LAZY_ATTRS),
    "__version__",
    "CODEC_REGISTRY",
    "FEC_REGISTRY",
    "SIMULATOR_REGISTRY",
    "simulate_reads",
    "init_plugins",
    "load_plugins",
    "install_registry_plugins",
    "ChannelConfig",
    "SequencePipeline",
    "encrypt_data",
    "decrypt_data",
    "compute_checksum",
]




def __getattr__(name: str) -> object:
    if name in {"encrypt_data", "decrypt_data", "compute_checksum"}:
        from .security import decrypt_data, encrypt_data, compute_checksum
        globals().update({
            "encrypt_data": encrypt_data,
            "decrypt_data": decrypt_data,
            "compute_checksum": compute_checksum,
        })
        return globals()[name]
    if name in _LAZY_ATTRS:
        from .options import EncodeOptions
        from .app_helpers import (
            EncodeResult,
            DecodeResult,
            perform_encoding,
            perform_decoding,
        )
        from .security import decrypt_data, encrypt_data, compute_checksum
        globals().update({
            "EncodeOptions": EncodeOptions,
            "EncodeResult": EncodeResult,
            "DecodeResult": DecodeResult,
            "perform_encoding": perform_encoding,
            "perform_decoding": perform_decoding,
            "encrypt_data": encrypt_data,
            "decrypt_data": decrypt_data,
            "compute_checksum": compute_checksum,
        })
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

