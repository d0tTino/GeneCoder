import builtins
import importlib
import sys
import argparse
from pathlib import Path
import pytest

from genecoder.cli.encode import process_single_encode
from genecoder.cli.decode import process_single_decode
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T


CASES = [
    (
        "genecoder.fountain_codec",
        "pyfinite",
        "encode_data_fountain",
        (b"data",),
        {},
        "pyfinite is required",
    ),
    (
        "genecoder.reed_solomon_codec",
        "reedsolo",
        "encode_data_rs",
        (b"data",),
        {"nsym": 5},
        "reedsolo is required",
    ),
    (
        "genecoder.ldpc_codec",
        "pyldpc",
        "encode_data_ldpc",
        (b"data",),
        {},
        "pyldpc is required",
    ),
    (
        "genecoder.raptorq_codec",
        "raptorq",
        "encode_data_raptorq",
        (b"data",),
        {"symbol_size": 4},
        "raptorq is required",
    ),
    (
        "genecoder.bch_codec",
        "bchlib",
        "encode_data_bch",
        (b"data",),
        {"m": 5, "t": 2},
        "bchlib is required",
    ),
]


@pytest.mark.parametrize("module_name, dep, func_name, args, kwargs, msg", CASES)
def test_optional_import_errors(monkeypatch, module_name, dep, func_name, args, kwargs, msg):
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.split(".")[0] == dep:
            raise ImportError(f"No module named {dep}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    sys.modules.pop(module_name, None)
    module = importlib.import_module(module_name)
    func = getattr(module, func_name)
    with pytest.raises(ImportError, match=msg):
        func(*args, **kwargs)


def _encode_args(fec: str) -> argparse.Namespace:
    return argparse.Namespace(
        method="base4_direct",
        add_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
        fec=fec,
        gc_min=0.45,
        gc_max=0.55,
        max_homopolymer=3,
        alphabet="base4",
        stream=False,
        capsule=None,
        export_csv=None,
    )


def _decode_args() -> argparse.Namespace:
    return argparse.Namespace(
        method="base4_direct",
        check_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
        alphabet="base4",
        stream=False,
        simulate_errors=0.0,
        simulator="d2sim",
    )


def test_cli_encode_missing_fec(tmp_path: Path) -> None:
    infile = tmp_path / "data.bin"
    infile.write_text("abc")
    args = _encode_args("ldpc")
    with pytest.raises(SystemExit):
        process_single_encode(str(infile), str(tmp_path / "out.fasta"), args)


import logging


def test_cli_decode_simulator_missing_binary(tmp_path: Path, caplog) -> None:
    input_file = tmp_path / "in.txt"
    input_file.write_text("sim")
    enc_args = _encode_args("triple_repeat")
    process_single_encode(str(input_file), str(tmp_path / "enc.fasta"), enc_args)

    dec_args = _decode_args()
    with caplog.at_level(logging.WARNING):
        process_single_decode(
            str(tmp_path / "enc.fasta"), str(tmp_path / "out.bin"), dec_args
        )
    assert any("falling back" in rec.message for rec in caplog.records)
