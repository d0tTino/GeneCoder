"""Event handler helpers for the Flet GUI."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Callable, Awaitable, Optional

import flet as ft

# Compatibility alias for color constants across Flet versions
COLORS = getattr(ft, "colors", getattr(ft, "Colors", None)) or ft.Colors

from .app_helpers import perform_decoding
from .constraint_fixer import fix_sequence
from .flet_helpers import parse_int_input
from .gc_constrained_encoder import calculate_gc_content
from .manifest import generate_manifest
from .options import EncodeOptions
from .utils import get_max_homopolymer_length
from .synthesis import SynthesisConstraints
from .cli.encode import reverse_complement
from .formats import to_fasta
from . import perform_encoding
from .flet_ws import ws_clients

logger = logging.getLogger(__name__)


decoded_bytes_to_save: bytes = b""


def make_encode_handler(
    *,
    page: ft.Page,
    selected_encode_input_file_path: ft.Ref[Optional[str]],
    encode_button: ft.ElevatedButton,
    encode_browse_button: ft.ElevatedButton,
    encode_progress_ring: ft.ProgressRing,
    encode_status_text: ft.Text,
    encode_orig_size_text: ft.Text,
    encode_dna_len_text: ft.Text,
    encode_comp_ratio_text: ft.Text,
    encode_bits_per_nt_text: ft.Text,
    encode_actual_gc_value: ft.Text,
    encode_actual_homopolymer_value: ft.Text,
    encode_dna_snippet_text: ft.Text,
    fixed_dna_snippet_text: ft.Text,
    fixed_metrics_text: ft.Text,
    encode_save_button: ft.ElevatedButton,
    encode_manifest_save_button: ft.ElevatedButton,
    encode_hidden_fasta_content: ft.Text,
    encode_hidden_manifest_content: ft.Text,
    encode_hidden_sequence: ft.Text,
    codeword_hist_image: ft.Image,
    nucleotide_freq_image: ft.Image,
    sequence_analysis_plot_image: ft.Image,
    analysis_status_text: ft.Text,
    fix_suggestion_text: ft.Text,
    app_tabs: ft.Tabs,
    method_dropdown: ft.Dropdown,
    parity_checkbox: ft.Checkbox,
    k_value_input: ft.TextField,
    fec_dropdown: ft.Dropdown,
    window_size_input: ft.TextField,
    step_size_input: ft.TextField,
    min_homopolymer_input: ft.TextField,
    alphabet_dropdown: ft.Dropdown,
    mirror_checkbox: ft.Checkbox,
    refresh_helix_view: Callable[[], None],
) -> Callable[[ft.ControlEvent], Awaitable[None]]:
    """Create the asynchronous encode event handler."""

    async def encode_data(e: ft.ControlEvent) -> None:
        # Disable buttons and show progress
        encode_button.disabled = True
        encode_browse_button.disabled = True
        encode_progress_ring.visible = True

        encode_status_text.value = "Processing..."
        encode_orig_size_text.value = "Original size: - bytes"
        encode_dna_len_text.value = "Encoded DNA length: - nucleotides"
        encode_comp_ratio_text.value = "Compression ratio: -"
        encode_bits_per_nt_text.value = "Bits per nucleotide: - bits/nt"
        encode_actual_gc_value.value = "-"
        encode_actual_homopolymer_value.value = "-"
        encode_dna_snippet_text.value = ""
        fixed_dna_snippet_text.value = ""
        fixed_metrics_text.value = ""
        encode_save_button.visible = False
        encode_manifest_save_button.visible = False
        encode_hidden_fasta_content.value = ""
        encode_hidden_manifest_content.value = ""

        codeword_hist_image.src_base64 = None
        nucleotide_freq_image.src_base64 = None
        sequence_analysis_plot_image.src_base64 = None
        analysis_status_text.value = "Encode data to view analysis plots."
        fix_suggestion_text.value = ""
        if len(app_tabs.tabs) > 2:
            app_tabs.tabs[2].disabled = True

        page.update()

        try:
            input_path = selected_encode_input_file_path.current
            if not input_path:
                encode_status_text.value = "Error: Please select an input file first."
                encode_status_text.color = COLORS.RED_ACCENT_700
                page.update()
                return

            with open(input_path, "rb") as f_in:
                input_data = await asyncio.to_thread(f_in.read)

            try:
                options = EncodeOptions(
                    method=method_dropdown.value,
                    add_parity=parity_checkbox.value,
                    k_value=parse_int_input(k_value_input.value, 7),
                    fec_method=fec_dropdown.value,
                    window_size=parse_int_input(window_size_input.value, 50),
                    step_size=parse_int_input(step_size_input.value, 10),
                    min_homopolymer_len=parse_int_input(min_homopolymer_input.value, 4),
                    alphabet=alphabet_dropdown.value,
                )
            except ValueError as ex:
                encode_status_text.value = f"Invalid numeric input: {ex}"
                encode_status_text.color = COLORS.RED_ACCENT_700
                page.update()
                return

            try:
                result = await asyncio.to_thread(perform_encoding, input_data, options)
            except ValueError as ex:
                encode_status_text.value = f"Error: {ex}"
                encode_status_text.color = COLORS.RED_ACCENT_700
                page.update()
                return

            final_fasta = result.fasta
            forward_seq = result.encoded_dna
            if mirror_checkbox.value:
                rc_seq = reverse_complement(forward_seq)
                rc_header = result.fasta.splitlines()[0][1:] + " mirror=rc"
                final_fasta += to_fasta(rc_seq, rc_header, line_width=80)
            encode_hidden_fasta_content.value = final_fasta
            encode_hidden_sequence.value = forward_seq
            encode_dna_snippet_text.value = forward_seq[:200]
            if ws_clients:
                async def _stream_bases(seq: str, step: int = 50) -> None:
                    for i in range(0, len(seq), step):
                        chunk = seq[i : i + step]
                        await asyncio.gather(*(c.send(chunk) for c in ws_clients))
                        await asyncio.sleep(0)

                asyncio.create_task(_stream_bases(forward_seq))
            encode_save_button.visible = True
            manifest = generate_manifest(
                os.path.basename(input_path), options, result.metrics
            )
            encode_hidden_manifest_content.value = json.dumps(manifest, indent=2)
            encode_manifest_save_button.visible = True

            metrics = result.metrics
            encode_orig_size_text.value = (
                f"Original size: {metrics['original_size']} bytes"
            )
            encode_dna_len_text.value = (
                f"Encoded DNA length: {metrics['dna_length']} nucleotides"
            )
            encode_comp_ratio_text.value = (
                f"Compression ratio: {metrics['compression_ratio']:.2f}"
            )
            encode_bits_per_nt_text.value = (
                f"Bits per nucleotide: {metrics['bits_per_nt']:.2f} bits/nt"
            )

            if options.method == "GC-Balanced":
                encode_actual_gc_value.value = f"{metrics['actual_gc']:.2%}"
                encode_actual_homopolymer_value.value = f"{metrics['max_homopolymer']}"
            else:
                encode_actual_gc_value.value = "N/A"
                encode_actual_homopolymer_value.value = "N/A"

            codeword_hist_image.src_base64 = result.plots.get("codeword_hist")
            nucleotide_freq_image.src_base64 = result.plots.get("nucleotide_freq")
            sequence_analysis_plot_image.src_base64 = result.plots.get(
                "sequence_analysis"
            )

            any_plot = any(result.plots.values())

            if any_plot:
                analysis_status_text.value = (
                    "All analysis plots generated successfully."
                )
                analysis_status_text.color = COLORS.GREEN_700
            else:
                analysis_status_text.value = (
                    "No analysis plots applicable or generated for the selected options."
                )
                analysis_status_text.color = COLORS.ORANGE_ACCENT_700
            if len(app_tabs.tabs) > 2:
                app_tabs.tabs[2].disabled = not any_plot

            info_msgs = list(result.info_messages)
            if options.method == "GC-Balanced" and options.add_parity:
                info_msgs.insert(0, "Info: 'Add Parity' not directly used by GC-Balanced.")
            status_prefix = " ".join(info_msgs)
            encode_status_text.value = (
                status_prefix + " " if status_prefix else ""
            ) + "Encoding successful! Click 'Save Encoded FASTA...' to save."
            encode_status_text.color = COLORS.GREEN_700

            gc_val = calculate_gc_content(forward_seq)
            hp_len = get_max_homopolymer_length(forward_seq)
            constraints = SynthesisConstraints()
            if (
                gc_val < 0.4
                or gc_val > 0.6
                or hp_len > constraints.max_homopolymer
            ):
                fixed = fix_sequence(
                    forward_seq,
                    target_gc_min=0.4,
                    target_gc_max=0.6,
                    max_homopolymer=constraints.max_homopolymer,
                )
                fix_gc = calculate_gc_content(fixed)
                fix_hp = get_max_homopolymer_length(fixed)
                fix_suggestion_text.value = (
                    f"Suggested fix GC {fix_gc:.2%}, max HP {fix_hp}."
                )
            else:
                fix_suggestion_text.value = ""

            refresh_helix_view()
            app_tabs.selected_index = 3
            page.update()

        except FileNotFoundError:
            encode_status_text.value = f"Error: Input file '{input_path}' not found."
            encode_status_text.color = COLORS.RED_ACCENT_700
        except OSError as ex:
            encode_status_text.value = f"I/O error during encoding: {ex}"
            encode_status_text.color = COLORS.RED_ACCENT_700
        except Exception as ex:  # pragma: no cover - unexpected
            logger.exception("Unexpected error during encoding")
            encode_status_text.value = f"An unexpected error occurred: {ex}"
            encode_status_text.color = COLORS.RED_ACCENT_700
            raise
        finally:
            encode_button.disabled = False
            encode_browse_button.disabled = False
            encode_progress_ring.visible = False
            page.update()

    return encode_data


def make_decode_handler(
    *,
    page: ft.Page,
    selected_decode_input_file_path: ft.Ref[Optional[str]],
    decode_button: ft.ElevatedButton,
    decode_browse_button: ft.ElevatedButton,
    decode_progress_ring: ft.ProgressRing,
    decode_status_text: ft.Text,
    decode_fec_info_text: ft.Text,
    decode_save_button: ft.ElevatedButton,
    decode_alphabet_dropdown: ft.Dropdown,
) -> Callable[[ft.ControlEvent], Awaitable[None]]:
    """Create the asynchronous decode event handler."""

    async def decode_file_data(e: ft.ControlEvent) -> None:
        global decoded_bytes_to_save
        decode_status_text.value = "Processing..."
        decode_progress_ring.visible = True
        decode_button.disabled = True
        decode_browse_button.disabled = True
        decode_save_button.visible = False
        decoded_bytes_to_save = b""
        page.update()

        try:
            input_path = selected_decode_input_file_path.current
            if not input_path:
                decode_status_text.value = "Error: Please select an input FASTA file first."
                decode_status_text.color = COLORS.RED_ACCENT_700
                page.update()
                return

            with open(input_path, "r", encoding="utf-8") as f_in:
                file_content_str = await asyncio.to_thread(f_in.read)

            try:
                result = await asyncio.to_thread(
                    perform_decoding, file_content_str, decode_alphabet_dropdown.value
                )
            except ValueError as ex:
                decode_status_text.value = f"Error: {ex}"
                decode_status_text.color = COLORS.RED_ACCENT_700
                page.update()
                return
            except Exception as ex:
                logger.exception("Unexpected error during decoding")
                decode_status_text.value = f"Unexpected error: {ex}"
                decode_status_text.color = COLORS.RED_ACCENT_700
                raise

            decoded_bytes_to_save = result.decoded_bytes
            decode_status_text.value = result.status_message
            decode_status_text.color = COLORS.GREEN_700
            if result.fec_info:
                decode_fec_info_text.value = result.fec_info
                decode_fec_info_text.color = COLORS.GREEN_700
            else:
                decode_fec_info_text.value = ""
            decode_save_button.visible = True

        except FileNotFoundError:
            decode_status_text.value = f"Error: Input file '{input_path}' not found."
            decode_status_text.color = COLORS.RED_ACCENT_700
        except OSError as ex:
            decode_status_text.value = f"I/O error: {ex}"
            decode_status_text.color = COLORS.RED_ACCENT_700
        except Exception as ex:  # pragma: no cover - unexpected
            logger.exception("Unexpected error during decode_file_data")
            decode_status_text.value = f"Critical error: {ex}"
            decode_status_text.color = COLORS.RED_ACCENT_700
            raise
        finally:
            decode_progress_ring.visible = False
            decode_button.disabled = False
            decode_browse_button.disabled = False
            page.update()

    return decode_file_data
