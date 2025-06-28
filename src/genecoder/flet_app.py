"""Interactive GUI for the GeneCoder toolkit.

This module builds a desktop-style application using `flet` that lets
users encode files into DNA sequences and decode them back.  The UI is
driven by the :func:`main` entry point which wires up event handlers for
encoding, decoding and plotting operations.

The application relies heavily on the :mod:`genecoder` package
(`encoders`, `huffman_coding`, `formats`, `error_detection`, and the
`plotting` utilities which themselves use `matplotlib`).  It runs most
heavy tasks asynchronously with :mod:`asyncio` so the interface remains
responsive.
See `docs/DEVELOPMENT_VISION.md` for how the GUI fits into the project's
integrated pipeline and extensible design.
"""
# Refer to Section IV of the Development Vision PDF for the UI architecture overview.

import flet as ft
import os
import asyncio  # For asynchronous operations
import json
from pathlib import Path
import logging
from typing import Optional, Any
try:
    import websockets
except Exception:  # pragma: no cover - optional dependency
    websockets = None

# Project module imports
from genecoder import (
    EncodeOptions,
    perform_encoding,
)
from genecoder.plugins import load_plugins
from genecoder.manifest import generate_manifest
from genecoder.flet_helpers import parse_int_input
from genecoder.app_helpers import perform_decoding
from genecoder.helix_view import show_helix
from genecoder.formats import from_fasta


logger = logging.getLogger(__name__)

GLOSSARY: dict[str, str] = {}
try:
    gloss_path = Path(__file__).resolve().parent.parent / "docs" / "glossary.json"
    with open(gloss_path, "r", encoding="utf-8") as f:
        GLOSSARY = json.load(f)
except Exception:
    pass


encode_fasta_data_to_save_ref: ft.Ref[Optional[str]] = ft.Ref[Optional[str]]()
decoded_bytes_to_save: bytes = b""

# --- optional WebSocket streaming setup ---
ws_clients: set[Any] = set()
if websockets:
    async def _ws_handler(websocket: Any) -> None:
        ws_clients.add(websocket)
        try:
            async for _ in websocket:
                pass
        finally:
            ws_clients.discard(websocket)

    asyncio.get_event_loop().create_task(websockets.serve(_ws_handler, "localhost", 8765))


def main(page: ft.Page) -> None:
    """Create the UI and register callbacks for Flet's event loop."""
    load_plugins()
    page.title = "GeneCoder"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    selected_encode_input_file_path: ft.Ref[Optional[str]] = ft.Ref[Optional[str]]()
    selected_encode_input_file_path.current = ""

    selected_decode_input_file_path: ft.Ref[Optional[str]] = ft.Ref[Optional[str]]()
    selected_decode_input_file_path.current = ""

    # --- Analysis Tab UI Controls (defined early for access in encode_data) ---
    codeword_hist_image: ft.Image = ft.Image(
        width=500,
        height=350,
        fit=ft.ImageFit.CONTAIN,
        tooltip="Huffman Codeword Length Histogram",
    )
    nucleotide_freq_image: ft.Image = ft.Image(
        width=500,
        height=350,
        fit=ft.ImageFit.CONTAIN,
        tooltip="Nucleotide Frequency Distribution",
    )
    sequence_analysis_plot_image: ft.Image = ft.Image(  # New image control
        width=600,
        height=400,
        fit=ft.ImageFit.CONTAIN,
        tooltip="Sequence GC & Homopolymer Analysis",
    )
    analysis_status_text: ft.Text = ft.Text(
        "Encode data to view analysis plots.", italic=True
    )

    # Container used for the Helix View tab. Filled when the tab is selected.
    helix_container: ft.Column = ft.Column()
    animate_checkbox: ft.Checkbox = ft.Checkbox(label="Animate", value=True)
    zoom_slider: ft.Slider = ft.Slider(
        min=0.5, max=2.0, value=1.0, divisions=15, width=200
    )
    fps_slider: ft.Slider = ft.Slider(
        min=10, max=60, value=60, divisions=10, width=200, label="FPS"
    )
    helix_length_input: ft.TextField = ft.TextField(
        label="Sequence Length",
        value="50",
        width=150,
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    helix_color_a: ft.TextField = ft.TextField(
        label="A", value="#ff5555", width=100
    )
    helix_color_c: ft.TextField = ft.TextField(
        label="C", value="#5555ff", width=100
    )
    helix_color_g: ft.TextField = ft.TextField(
        label="G", value="#55ff55", width=100
    )
    helix_color_t: ft.TextField = ft.TextField(
        label="T", value="#ffff55", width=100
    )
    helix_controls: ft.Row = ft.Row(
        [
            helix_length_input,
            helix_color_a,
            helix_color_c,
            helix_color_g,
            helix_color_t,
        ],
        alignment=ft.MainAxisAlignment.START,
    )


    window_size_input: ft.TextField = ft.TextField(
        label="GC Window Size",
        value="50",
        width=120,
        keyboard_type=ft.KeyboardType.NUMBER,
        tooltip=GLOSSARY.get("GC content"),
    )
    step_size_input: ft.TextField = ft.TextField(
        label="Step",
        value="10",
        width=100,
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    min_homopolymer_input: ft.TextField = ft.TextField(
        label="Min Homopolymer Length",
        value="4",
        width=180,
        keyboard_type=ft.KeyboardType.NUMBER,
        tooltip=GLOSSARY.get("Homopolymer"),
    )

    # --- Encode Tab UI Controls ---
    encode_selected_input_file_text: ft.Text = ft.Text(
        "No file selected.", italic=True
    )
    
    def on_encode_file_picker_result(e: ft.FilePickerResultEvent) -> None:

        if e.files and len(e.files) > 0:
            selected_encode_input_file_path.current = e.files[0].path
            encode_selected_input_file_text.value = (
                f"Selected: {os.path.basename(e.files[0].name)}"
            )
        else:
            selected_encode_input_file_path.current = ""
            encode_selected_input_file_text.value = (
                "File selection cancelled or failed."
            )
        page.update()

    encode_file_picker: ft.FilePicker = ft.FilePicker(
        on_result=on_encode_file_picker_result
    )
    page.overlay.append(encode_file_picker)

    def _open_encode_file_picker(_: ft.ControlEvent) -> None:
        encode_file_picker.pick_files(
            allow_multiple=False, dialog_title="Select Input File for Encoding"
        )

    encode_browse_button: ft.ElevatedButton = ft.ElevatedButton(
        "Browse File",
        icon=ft.icons.FOLDER_OPEN,
        on_click=_open_encode_file_picker,
    )

    method_dropdown: ft.Dropdown = ft.Dropdown(
        label="Encoding Method",
        options=[
            ft.dropdown.Option("Base-4 Direct"),
            ft.dropdown.Option("Huffman"),
            ft.dropdown.Option("GC-Balanced"),
        ],
        value="Base-4 Direct",
    )

    alphabet_dropdown: ft.Dropdown = ft.Dropdown(
        label="Alphabet",
        options=[
            ft.dropdown.Option("base4"),
            ft.dropdown.Option("base5"),
            ft.dropdown.Option("base6"),
        ],
        value="base4",
    )

    k_value_input: ft.TextField = ft.TextField(
        label="k-value (for parity)",
        value="7",
        width=150,
        disabled=True,
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    def _toggle_k_value(e: ft.ControlEvent) -> None:
        k_value_input.disabled = not e.control.value
        page.update()

    parity_checkbox: ft.Checkbox = ft.Checkbox(
        label="Add Parity", value=False, on_change=_toggle_k_value
    )

    def on_fec_change(e: ft.ControlEvent) -> None:
        """Toggle parity checkbox based on selected FEC."""
        selected = e.control.value
        if selected in ("Hamming(7,4)", "Reed-Solomon"):
            parity_checkbox.value = False
            parity_checkbox.disabled = True
            k_value_input.disabled = True
        else:
            parity_checkbox.disabled = False
            k_value_input.disabled = not parity_checkbox.value
        page.update()

    fec_dropdown: ft.Dropdown = ft.Dropdown(
        label="FEC Method",
        options=[
            ft.dropdown.Option("None"),
            ft.dropdown.Option("Triple-Repeat"),
            ft.dropdown.Option("Hamming(7,4)"),
            ft.dropdown.Option("Reed-Solomon"),
        ],
        value="None",
        on_change=on_fec_change,
        tooltip=GLOSSARY.get("Forward Error Correction (FEC)"),
    )

    encode_button: ft.ElevatedButton = ft.ElevatedButton("Encode")

    encode_status_text: ft.Text = ft.Text("", selectable=True)
    encode_orig_size_text: ft.Text = ft.Text("Original size: - bytes")
    encode_dna_len_text: ft.Text = ft.Text("Encoded DNA length: - nucleotides")
    encode_comp_ratio_text: ft.Text = ft.Text("Compression ratio: -")
    encode_bits_per_nt_text: ft.Text = ft.Text("Bits per nucleotide: - bits/nt")
    encode_actual_gc_text: ft.Text = ft.Text("Actual GC content (payload): -")
    encode_actual_homopolymer_text: ft.Text = ft.Text(
        "Actual max homopolymer (payload): -"
    )
    encode_progress_ring: ft.ProgressRing = ft.ProgressRing(
        visible=False, width=20, height=20
    )  # Progress indicator

    encode_dna_snippet_text: ft.TextField = ft.TextField(
        label="DNA Snippet (first 200 chars)",
        read_only=True,
        multiline=True,
        max_lines=3,
        value="",
        width=500,
    )

    encode_save_button: ft.ElevatedButton = ft.ElevatedButton(
        "Save Encoded FASTA...", icon=ft.icons.SAVE, visible=False
    )

    encode_manifest_save_button: ft.ElevatedButton = ft.ElevatedButton(
        "Save Manifest...",
        icon=ft.icons.SAVE,
        visible=False,
    )

    encode_hidden_fasta_content: ft.Text = ft.Text(
        ref=encode_fasta_data_to_save_ref, visible=False, value=""
    )
    encode_manifest_to_save_ref: ft.Ref[Optional[str]] = ft.Ref[Optional[str]]()
    encode_hidden_manifest_content: ft.Text = ft.Text(
        ref=encode_manifest_to_save_ref,
        visible=False,
        value="",
    )
    encode_hidden_sequence: ft.Text = ft.Text(visible=False, value="")

    # --- Main App Structure (Tabs) defined here so encode_data can access app_tabs.tabs[2] ---
    # This is a forward declaration of sorts for app_tabs, its full definition with content is later.
    app_tabs: ft.Tabs = ft.Tabs()

    # --- Encode Event Handlers ---
    async def encode_data(e: ft.ControlEvent) -> None:
        """
        Handles the encoding process when the 'Encode' button is clicked.

        This asynchronous function performs the following steps:
        1. Disables UI controls (buttons, progress ring) to prevent concurrent operations.
        2. Resets UI elements (status texts, image displays).
        3. Validates user inputs (file selection, parity k-value).
        4. Reads input file data asynchronously.
        5. Applies the selected encoding method (Base-4 Direct, Huffman, GC-Balanced)
           asynchronously using `asyncio.to_thread`.
        6. Optionally applies Triple-Repeat, Hamming(7,4), or Reed-Solomon FEC if selected,
           also asynchronously.
        7. Constructs FASTA header and formats the output.
        8. Calculates and displays encoding metrics.
        9. Generates and displays analysis plots (Huffman codeword lengths, nucleotide frequencies)
           asynchronously if applicable.
        10. Updates status messages and re-enables UI controls in a `finally` block.
        """
        # The encode workflow does not use the decoded bytes buffer

        # Disable buttons and show progress
        encode_button.disabled = True
        encode_browse_button.disabled = True
        encode_progress_ring.visible = True

        encode_status_text.value = "Processing..."
        encode_orig_size_text.value = "Original size: - bytes"
        encode_dna_len_text.value = "Encoded DNA length: - nucleotides"
        encode_comp_ratio_text.value = "Compression ratio: -"
        encode_bits_per_nt_text.value = "Bits per nucleotide: - bits/nt"
        encode_actual_gc_text.value = "Actual GC content (payload): -"
        encode_actual_homopolymer_text.value = "Actual max homopolymer (payload): -"
        encode_dna_snippet_text.value = ""
        encode_save_button.visible = False
        encode_manifest_save_button.visible = False
        encode_hidden_fasta_content.value = ""
        encode_hidden_manifest_content.value = ""

        codeword_hist_image.src_base64 = None
        nucleotide_freq_image.src_base64 = None
        sequence_analysis_plot_image.src_base64 = None  # Clear new plot
        analysis_status_text.value = "Encode data to view analysis plots."
        if len(app_tabs.tabs) > 2:
            app_tabs.tabs[2].disabled = True

        page.update()

        try:
            input_path = selected_encode_input_file_path.current
            if not input_path:
                encode_status_text.value = "Error: Please select an input file first."
                encode_status_text.color = ft.colors.RED_ACCENT_700
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
                encode_status_text.color = ft.colors.RED_ACCENT_700
                page.update()
                return

            try:
                result = await asyncio.to_thread(perform_encoding, input_data, options)
            except ValueError as ex:
                encode_status_text.value = f"Error: {ex}"
                encode_status_text.color = ft.colors.RED_ACCENT_700
                page.update()
                return

            encode_hidden_fasta_content.value = result.fasta
            encode_hidden_sequence.value = result.encoded_dna
            encode_dna_snippet_text.value = result.encoded_dna[:200]
            if ws_clients:
                async def _broadcast(msg: str) -> None:
                    await asyncio.gather(*(c.send(msg) for c in ws_clients))

                asyncio.create_task(_broadcast(result.encoded_dna))
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
                encode_actual_gc_text.value = (
                    f"Actual GC content (payload, pre-FEC): {metrics['actual_gc']:.2%}"
                )
                encode_actual_homopolymer_text.value = f"Actual max homopolymer (payload, pre-FEC): {metrics['max_homopolymer']}"
            else:
                encode_actual_gc_text.value = "Actual GC content (payload): N/A"
                encode_actual_homopolymer_text.value = (
                    "Actual max homopolymer (payload): N/A"
                )

            codeword_hist_image.src_base64 = result.plots.get("codeword_hist")
            nucleotide_freq_image.src_base64 = result.plots.get("nucleotide_freq")
            sequence_analysis_plot_image.src_base64 = result.plots.get(
                "sequence_analysis"
            )

            # Compute after populating result.plots so checks use a stable value
            any_plot = any(result.plots.values())

            if any_plot:
                analysis_status_text.value = (
                    "All analysis plots generated successfully."
                )
                analysis_status_text.color = ft.colors.GREEN_700
            else:
                analysis_status_text.value = "No analysis plots applicable or generated for the selected options."
                analysis_status_text.color = ft.colors.ORANGE_ACCENT_700
            if len(app_tabs.tabs) > 2:
                app_tabs.tabs[2].disabled = not any_plot

            info_msgs = list(result.info_messages)
            if options.method == "GC-Balanced" and options.add_parity:
                info_msgs.insert(
                    0, "Info: 'Add Parity' not directly used by GC-Balanced."
                )
            status_prefix = " ".join(info_msgs)
            encode_status_text.value = (
                status_prefix + " " if status_prefix else ""
            ) + "Encoding successful! Click 'Save Encoded FASTA...' to save."
            encode_status_text.color = ft.colors.GREEN_700

        except FileNotFoundError:
            encode_status_text.value = f"Error: Input file '{input_path}' not found."
            encode_status_text.color = ft.colors.RED_ACCENT_700
        except OSError as ex:
            encode_status_text.value = f"I/O error during encoding: {ex}"
            encode_status_text.color = ft.colors.RED_ACCENT_700
        except Exception as ex:
            logger.exception("Unexpected error during encoding")
            encode_status_text.value = f"An unexpected error occurred: {ex}"
            encode_status_text.color = ft.colors.RED_ACCENT_700
            raise
        finally:
            # Re-enable buttons and hide progress
            encode_button.disabled = False
            encode_browse_button.disabled = False
            encode_progress_ring.visible = False
            page.update()

    encode_button.on_click = encode_data

    async def on_encode_save_file_result(e: ft.FilePickerResultEvent) -> None:  # Made async for consistency, though not strictly needed here

        if e.path:
            try:
                with open(e.path, "w", encoding="utf-8") as f_out:
                    f_out.write(encode_hidden_fasta_content.value)
                encode_status_text.value = (
                    f"Encoded file saved successfully to: {e.path}"
                )
                encode_status_text.color = ft.colors.GREEN_700
            except OSError as ex:
                encode_status_text.value = f"Error saving file: {ex}"
                encode_status_text.color = ft.colors.RED_ACCENT_700
            except Exception as ex:
                logger.exception("Unexpected error while saving encoded FASTA")
                encode_status_text.value = f"Unexpected error saving file: {ex}"
                encode_status_text.color = ft.colors.RED_ACCENT_700
                raise
        else:
            encode_status_text.value = "Save operation cancelled by user."
            encode_status_text.color = ft.colors.AMBER_ACCENT_700
        page.update()

    encode_save_file_picker: ft.FilePicker = ft.FilePicker(
        on_result=on_encode_save_file_result
    )
    page.overlay.append(encode_save_file_picker)

    def _open_encode_save_picker(_: ft.ControlEvent) -> None:
        encode_save_file_picker.save_file(
            dialog_title="Save Encoded FASTA File",
            file_name="encoded_output.fasta",
            allowed_extensions=["fasta", "fa"],
        )

    encode_save_button.on_click = _open_encode_save_picker

    async def on_manifest_save_file_result(e: ft.FilePickerResultEvent) -> None:
        if e.path:
            try:
                with open(e.path, "w", encoding="utf-8") as f_out:
                    f_out.write(encode_hidden_manifest_content.value)
                encode_status_text.value = f"Manifest saved successfully to: {e.path}"
                encode_status_text.color = ft.colors.GREEN_700
            except OSError as ex:
                encode_status_text.value = f"Error saving manifest: {ex}"
                encode_status_text.color = ft.colors.RED_ACCENT_700
            except Exception as ex:
                logger.exception("Unexpected error while saving manifest")
                encode_status_text.value = f"Unexpected error saving manifest: {ex}"
                encode_status_text.color = ft.colors.RED_ACCENT_700
                raise
        else:
            encode_status_text.value = "Save operation cancelled by user."
            encode_status_text.color = ft.colors.AMBER_ACCENT_700
        page.update()

    manifest_file_picker: ft.FilePicker = ft.FilePicker(
        on_result=on_manifest_save_file_result
    )
    page.overlay.append(manifest_file_picker)

    def _open_manifest_save_picker(_: ft.ControlEvent) -> None:
        manifest_file_picker.save_file(
            dialog_title="Save Manifest File",
            file_name="encoded_output.manifest.json",
            allowed_extensions=["json"],
        )

    encode_manifest_save_button.on_click = _open_manifest_save_picker

    # --- Decode Tab UI Controls & Logic ---
    decode_selected_input_file_text: ft.Text = ft.Text(
        "No FASTA file selected.", italic=True
    )
    decode_status_text: ft.Text = ft.Text(
        "", selectable=True
    )  # Main status for decoding results
    decode_fec_info_text: ft.Text = ft.Text(
        "", selectable=True, color=ft.colors.BLUE_GREY_500
    )  # Displays FEC correction/error counts
    decode_progress_ring: ft.ProgressRing = ft.ProgressRing(
        visible=False, width=20, height=20
    )  # Progress indicator

    decode_save_button: ft.ElevatedButton = ft.ElevatedButton(
        "Save Decoded File...", icon=ft.icons.SAVE, visible=False
    )

    decode_button: ft.ElevatedButton = ft.ElevatedButton("Decode")

    decode_stream_checkbox: ft.Checkbox = ft.Checkbox(
        label="Stream large files", value=False
    )
    decode_alphabet_dropdown: ft.Dropdown = ft.Dropdown(
        label="Alphabet",
        options=[
            ft.dropdown.Option("base4"),
            ft.dropdown.Option("base5"),
            ft.dropdown.Option("base6"),
        ],
        value="base4",
    )

    async def on_decode_file_picker_result(e: ft.FilePickerResultEvent) -> None:  # Made async

        if e.files and len(e.files) > 0:
            selected_decode_input_file_path.current = e.files[0].path
            decode_selected_input_file_text.value = (
                f"Selected: {os.path.basename(e.files[0].name)}"
            )
        else:
            selected_decode_input_file_path.current = ""
            decode_selected_input_file_text.value = (
                "File selection cancelled or failed."
            )
        decode_status_text.value = ""
        decode_save_button.visible = False
        page.update()

    decode_file_picker: ft.FilePicker = ft.FilePicker(
        on_result=on_decode_file_picker_result
    )
    page.overlay.append(decode_file_picker)

    def _open_decode_file_picker(_: ft.ControlEvent) -> None:
        decode_file_picker.pick_files(
            allow_multiple=False,
            dialog_title="Select FASTA File for Decoding",
            allowed_extensions=["fasta", "fa", "txt"],
        )

    decode_browse_button: ft.ElevatedButton = ft.ElevatedButton(
        "Browse FASTA File",
        icon=ft.icons.FOLDER_OPEN,
        on_click=_open_decode_file_picker,
    )

    async def decode_file_data(e: ft.ControlEvent) -> None:
        """Decode an input FASTA file using :func:`perform_decoding`."""
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
                decode_status_text.value = (
                    "Error: Please select an input FASTA file first."
                )
                decode_status_text.color = ft.colors.RED_ACCENT_700
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
                decode_status_text.color = ft.colors.RED_ACCENT_700
                page.update()
                return
            except Exception as ex:
                logger.exception("Unexpected error during decoding")
                decode_status_text.value = f"Unexpected error: {ex}"
                decode_status_text.color = ft.colors.RED_ACCENT_700
                raise

            decoded_bytes_to_save = result.decoded_bytes
            decode_status_text.value = result.status_message
            decode_status_text.color = ft.colors.GREEN_700
            if result.fec_info:
                decode_fec_info_text.value = result.fec_info
                decode_fec_info_text.color = ft.colors.GREEN_700
            else:
                decode_fec_info_text.value = ""
            decode_save_button.visible = True

        except FileNotFoundError:
            decode_status_text.value = f"Error: Input file '{input_path}' not found."
            decode_status_text.color = ft.colors.RED_ACCENT_700
        except OSError as ex:
            decode_status_text.value = f"I/O error: {ex}"
            decode_status_text.color = ft.colors.RED_ACCENT_700
        except Exception as ex:
            logger.exception("Unexpected error during decode_file_data")
            decode_status_text.value = f"Critical error: {ex}"
            decode_status_text.color = ft.colors.RED_ACCENT_700
            raise
        finally:
            decode_progress_ring.visible = False
            decode_button.disabled = False
            decode_browse_button.disabled = False
            page.update()

    decode_button.on_click = decode_file_data

    async def on_save_decoded_file_result(e: ft.FilePickerResultEvent) -> None:  # Made async
        if e.path:
            try:
                with open(e.path, "wb") as f_out:
                    f_out.write(decoded_bytes_to_save)
                decode_status_text.value = (
                    f"Decoded file saved successfully to {e.path}"
                )
            except OSError as ex:
                decode_status_text.value = f"Error saving decoded file: {ex}"
            except Exception as ex:
                logger.exception("Unexpected error while saving decoded file")
                decode_status_text.value = f"Unexpected error saving decoded file: {ex}"
                decode_status_text.color = ft.colors.RED_ACCENT_700
                raise
        else:
            decode_status_text.value = "Save decoded file cancelled."
        page.update()

    save_decoded_file_picker: ft.FilePicker = ft.FilePicker(
        on_result=on_save_decoded_file_result
    )
    page.overlay.append(save_decoded_file_picker)

    def _open_save_decoded_picker(_: ft.ControlEvent) -> None:
        save_decoded_file_picker.save_file(
            dialog_title="Save Decoded File", file_name="decoded_output.bin"
        )

    decode_save_button.on_click = _open_save_decoded_picker

    decode_tab_content_column: ft.Column = ft.Column(
        controls=[
            ft.Row(
                [decode_browse_button, decode_selected_input_file_text],
                alignment=ft.MainAxisAlignment.START,
            ),
            ft.Row([decode_button, decode_progress_ring]),  # Added progress ring
            decode_alphabet_dropdown,
            decode_stream_checkbox,
            ft.Divider(),
            ft.Text("Status:", weight=ft.FontWeight.BOLD),
            decode_status_text,
            decode_fec_info_text,
            decode_save_button,
        ],
        spacing=15,
        scroll=ft.ScrollMode.AUTO,
    )

    # --- Layout for Analysis Tab ---
    analysis_tab_content_column: ft.Column = ft.Column(
        controls=[
            analysis_status_text,
            ft.Divider(),
            ft.Text("Huffman Codeword Length Histogram:", weight=ft.FontWeight.BOLD),
            codeword_hist_image,
            ft.Divider(),
            ft.Text(
                "Nucleotide Frequency Distribution (Encoded Sequence):",
                weight=ft.FontWeight.BOLD,
            ),
            nucleotide_freq_image,
            ft.Divider(),  # New divider
            ft.Text(
                "Sequence GC & Homopolymer Analysis:", weight=ft.FontWeight.BOLD
            ),  # New title
            ft.Row(
                [
                    window_size_input,
                    step_size_input,
                    min_homopolymer_input,
                ],
                alignment=ft.MainAxisAlignment.START,
            ),
            sequence_analysis_plot_image,  # New plot image
        ],
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
    )

    # --- Main App Structure (Tabs) ---
    # Analysis tab needs to be referenced later to enable/disable
    analysis_tab: ft.Tab = ft.Tab(
        text="Analysis",
        icon=ft.icons.ANALYTICS_OUTLINED,
        content=ft.Container(
            analysis_tab_content_column,
            padding=10,
            alignment=ft.alignment.top_left,
        ),
    )
    analysis_tab.disabled = True  # Initially disabled until data is encoded

    # Ensure app_tabs is defined before encode_data tries to access it
    app_tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(
                text="Encode",
                icon=ft.icons.SEND_AND_ARCHIVE_OUTLINED,
                content=ft.Container(
                    ft.Column(
                        controls=[
                            ft.Row(
                                [encode_browse_button, encode_selected_input_file_text]
                            ),
                            method_dropdown,
                            alphabet_dropdown,
                            ft.Row([parity_checkbox, k_value_input]),
                            fec_dropdown,
                            ft.Row(
                                [encode_button, encode_progress_ring]
                            ),  # Added progress ring
                            ft.Divider(),
                            ft.Text("Metrics:", weight=ft.FontWeight.BOLD),
                            encode_orig_size_text,
                            encode_dna_len_text,
                            encode_comp_ratio_text,
                            encode_bits_per_nt_text,
                            encode_actual_gc_text,
                            encode_actual_homopolymer_text,
                            ft.Text("Output Preview:", weight=ft.FontWeight.BOLD),
                            encode_dna_snippet_text,
                            encode_save_button,
                            encode_manifest_save_button,
                            encode_status_text,
                            encode_hidden_fasta_content,
                            encode_hidden_manifest_content,
                            encode_hidden_sequence,
                        ],
                        spacing=15,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    padding=10,
                    alignment=ft.alignment.TOP_LEFT,
                ),
            ),
            ft.Tab(
                text="Decode",
                icon=ft.icons.UNARCHIVE_OUTLINED,
                content=ft.Container(
                    decode_tab_content_column,
                    padding=10,
                    alignment=ft.alignment.top_left,
                ),
            ),
            #(analysis tab defined above to allow setting disabled after init)
            analysis_tab,
            ft.Tab(
                text="Helix View",
                icon=ft.icons.DNA,
                content=ft.Container(
                    ft.Column([
                        helix_controls,
                        helix_container,
                    ], spacing=10),
                    padding=10,
                    alignment=ft.alignment.top_left,
                ),
            ),
        ],
        expand=True,
    )

    def refresh_helix_view(_: ft.ControlEvent | None = None) -> None:
        dna_seq = ""
        if encode_hidden_fasta_content.value:
            parsed = from_fasta(encode_hidden_fasta_content.value)
            if parsed:
                dna_seq = parsed[0][1]
        helix_container.controls.clear()
        helix_container.controls.append(
            ft.Row([
                animate_checkbox,
                ft.Text("Zoom:"),
                zoom_slider,
                ft.Text("FPS:"),
                fps_slider,
            ])
        )
        helix_container.controls.append(
            show_helix(
                dna_seq,
                animate=animate_checkbox.value,
                zoom=zoom_slider.value,
                fps=fps_slider.value,
                ws_url="ws://localhost:8765" if ws_clients else None,
            )
        )
        page.update()

    animate_checkbox.on_change = refresh_helix_view
    zoom_slider.on_change = refresh_helix_view
    fps_slider.on_change = refresh_helix_view

    def on_tab_change(e: ft.ControlEvent) -> None:
        if app_tabs.selected_index == 3:
            refresh_helix_view()


        page.update()

    app_tabs.on_change = on_tab_change

    page.add(app_tabs)  # Add tabs to page first
    page.update()


if __name__ == "__main__":
    ft.app(target=main)
