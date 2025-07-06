import asyncio
import types

import pytest

from genecoder.flet_handlers import (
    make_encode_handler,
    make_decode_handler,
)

ft = pytest.importorskip("flet")


class DummyPage:
    def update(self) -> None:  # noqa: D401 - minimal stub
        pass


def control(**kwargs):
    return types.SimpleNamespace(**kwargs)


def test_make_encode_handler_calls_perform_encoding(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    called = {}

    def fake_perform_encoding(data: bytes, opts: object) -> object:
        called["data"] = data
        return types.SimpleNamespace(
            fasta=">seq\nAC",
            encoded_dna="AC",
            plots={},
            metrics={
                "original_size": len(data),
                "dna_length": 2,
                "compression_ratio": 1.0,
                "bits_per_nt": 2.0,
                "actual_gc": 0.5,
                "max_homopolymer": 1,
            },
            info_messages=[],
        )

    monkeypatch.setattr("genecoder.flet_handlers.perform_encoding", fake_perform_encoding)
    monkeypatch.setattr("genecoder.flet_handlers.generate_manifest", lambda *a, **k: {})

    inp = tmp_path / "data.bin"
    inp.write_bytes(b"x")

    handler = make_encode_handler(
        page=DummyPage(),
        selected_encode_input_file_path=types.SimpleNamespace(current=str(inp)),
        encode_button=control(disabled=False),
        encode_browse_button=control(disabled=False),
        encode_progress_ring=control(visible=False),
        encode_status_text=control(value="", color=""),
        encode_orig_size_text=control(value=""),
        encode_dna_len_text=control(value=""),
        encode_comp_ratio_text=control(value=""),
        encode_bits_per_nt_text=control(value=""),
        encode_actual_gc_value=control(value=""),
        encode_actual_homopolymer_value=control(value=""),
        encode_dna_snippet_text=control(value=""),
        fixed_dna_snippet_text=control(value=""),
        fixed_metrics_text=control(value=""),
        encode_save_button=control(visible=False),
        encode_manifest_save_button=control(visible=False),
        encode_hidden_fasta_content=control(value=""),
        encode_hidden_manifest_content=control(value=""),
        encode_hidden_sequence=control(value=""),
        codeword_hist_image=control(src_base64=None),
        nucleotide_freq_image=control(src_base64=None),
        sequence_analysis_plot_image=control(src_base64=None),
        analysis_status_text=control(value="", color=""),
        fix_suggestion_text=control(value=""),
        app_tabs=types.SimpleNamespace(
            tabs=[types.SimpleNamespace(disabled=False) for _ in range(3)],
            selected_index=0,
        ),
        method_dropdown=types.SimpleNamespace(value="Base-4 Direct"),
        parity_checkbox=types.SimpleNamespace(value=False),
        k_value_input=types.SimpleNamespace(value="7"),
        fec_dropdown=types.SimpleNamespace(value="None"),
        window_size_input=types.SimpleNamespace(value="50"),
        step_size_input=types.SimpleNamespace(value="10"),
        min_homopolymer_input=types.SimpleNamespace(value="4"),
        alphabet_dropdown=types.SimpleNamespace(value="base4"),
        mirror_checkbox=types.SimpleNamespace(value=False),
        refresh_helix_view=lambda: None,
    )

    asyncio.run(handler(None))
    assert called["data"] == b"x"


def test_make_decode_handler_sets_global(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_perform_decoding(fasta: str, alphabet: str) -> object:
        return types.SimpleNamespace(decoded_bytes=b"out", status_message="ok", fec_info="")

    monkeypatch.setattr("genecoder.flet_handlers.perform_decoding", fake_perform_decoding)

    fasta = tmp_path / "seq.fa"
    fasta.write_text(">s\nAC")

    handler = make_decode_handler(
        page=DummyPage(),
        selected_decode_input_file_path=types.SimpleNamespace(current=str(fasta)),
        decode_button=control(disabled=False),
        decode_browse_button=control(disabled=False),
        decode_progress_ring=control(visible=False),
        decode_status_text=control(value="", color=""),
        decode_fec_info_text=control(value="", color=""),
        decode_save_button=control(visible=False),
        decode_alphabet_dropdown=types.SimpleNamespace(value="base4"),
    )

    asyncio.run(handler(None))
    from genecoder import flet_handlers

    assert flet_handlers.decoded_bytes_to_save == b"out"
