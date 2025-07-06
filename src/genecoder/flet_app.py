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
import logging
import webbrowser
from typing import Optional

from genecoder.flet_ws import ws_clients  # noqa: F401 - start server on import
from genecoder.flet_handlers import (
    make_decode_handler,
    make_encode_handler,
    decoded_bytes_to_save,
)

# Project module imports
from genecoder.plugins import load_plugins
from genecoder.helix_view import show_helix_ui
from genecoder.formats import from_fasta
from genecoder.cli.encode import reverse_complement
from genecoder.glossary_tooltips import (
    load_glossary,
    load_glossary_full,
    wrap_glossary_terms,
    glossary_modal_text,
)
from genecoder.gc_constrained_encoder import calculate_gc_content
from genecoder.utils import get_max_homopolymer_length
from genecoder.synthesis import SynthesisConstraints
from genecoder.constraint_fixer import fix_sequence


logger = logging.getLogger(__name__)

try:
    GLOSSARY: dict[str, str] = load_glossary()
    GLOSSARY_FULL: dict[str, str] = load_glossary_full()
except Exception:
    GLOSSARY = {}
    GLOSSARY_FULL = {}


encode_fasta_data_to_save_ref: ft.Ref[Optional[str]] = ft.Ref[Optional[str]]()


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

    # Container used for the Visualizer tab. Filled when the tab is selected.
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
        label=ft.Row(
            [
                ft.Text("GC Window Size ("),
                glossary_modal_text("GC content", page, GLOSSARY, GLOSSARY_FULL),
                ft.Text(")"),
            ],
            spacing=0,
        ),
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
        label=ft.Row(
            [
                ft.Text("Min "),
                glossary_modal_text(
                    "Homopolymer", page, GLOSSARY, GLOSSARY_FULL
                ),
                ft.Text(" Length"),
            ],
            spacing=0,
        ),
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

    def on_encode_file_drop(e: ft.ControlEvent) -> None:
        """Handle files dropped onto the encode drop zone."""
        files = getattr(e, "files", None)
        if files and len(files) > 0:
            selected_encode_input_file_path.current = files[0].path
            encode_selected_input_file_text.value = (
                f"Selected: {os.path.basename(files[0].name)}"
            )
        else:
            selected_encode_input_file_path.current = ""
            encode_selected_input_file_text.value = "File drop cancelled."
        page.update()

    icons = getattr(ft, "icons", ft.Icons)
    colors = getattr(ft, "colors", ft.Colors)
    encode_browse_button: ft.ElevatedButton = ft.ElevatedButton(
        "Browse File",
        icon=getattr(icons, "FOLDER_OPEN", None),
        on_click=_open_encode_file_picker,
    )

    DropTarget = getattr(ft, "DropTarget", getattr(ft, "DragTarget", None))
    encode_drop_zone = None
    if DropTarget:
        drop_kwargs = {
            "on_drop" if hasattr(DropTarget, "on_drop") else "on_accept": on_encode_file_drop
        }
        encode_drop_zone = DropTarget(
            content=ft.Container(
                ft.Text("Drop file"),
                width=150,
                height=80,
                border=ft.border.all(1, colors.BLUE_GREY_200),
                alignment=ft.alignment.center,
            ),
            **drop_kwargs,
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
        label=wrap_glossary_terms("FEC Method", GLOSSARY),
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

    mirror_checkbox: ft.Checkbox = ft.Checkbox(
        label="Mirror",
        value=False,
        tooltip=GLOSSARY.get("Mirror"),
    )

    encode_button: ft.ElevatedButton = ft.ElevatedButton("Encode")

    encode_status_text: ft.Text = ft.Text("", selectable=True)
    fix_suggestion_text: ft.Text = ft.Text("", selectable=True)
    fix_button: ft.ElevatedButton = ft.ElevatedButton("Fix Sequence")
    fixed_dna_snippet_text: ft.TextField = ft.TextField(
        label="Fixed DNA Snippet (first 200 chars)",
        read_only=True,
        multiline=True,
        max_lines=3,
        value="",
        width=500,
    )
    fixed_metrics_text: ft.Text = ft.Text("", selectable=True)
    encode_orig_size_text: ft.Text = ft.Text("Original size: - bytes")
    encode_dna_len_text: ft.Text = ft.Text("Encoded DNA length: - nucleotides")
    encode_comp_ratio_text: ft.Text = ft.Text("Compression ratio: -")
    encode_bits_per_nt_text: ft.Text = ft.Text("Bits per nucleotide: - bits/nt")
    encode_actual_gc_value: ft.Text = ft.Text("-")
    encode_actual_gc_text: ft.Row = ft.Row(
        [
            ft.Text("Actual "),
            glossary_modal_text("GC content", page, GLOSSARY, GLOSSARY_FULL),
            ft.Text(" (payload): "),
            encode_actual_gc_value,
        ],
        spacing=0,
    )
    encode_actual_homopolymer_value: ft.Text = ft.Text("-")
    encode_actual_homopolymer_text: ft.Row = ft.Row(
        [
            ft.Text("Actual max "),
            glossary_modal_text("Homopolymer", page, GLOSSARY, GLOSSARY_FULL),
            ft.Text(" (payload): "),
            encode_actual_homopolymer_value,
        ],
        spacing=0,
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
        "Save Encoded FASTA...", icon=getattr(icons, "SAVE", None), visible=False
    )

    encode_manifest_save_button: ft.ElevatedButton = ft.ElevatedButton(
        "Save Manifest...",
        icon=getattr(icons, "SAVE", None),
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

    def refresh_helix_view(_: ft.ControlEvent | None = None) -> None:
        dna_seq = ""
        if encode_hidden_fasta_content.value:
            parsed = from_fasta(encode_hidden_fasta_content.value)
            if parsed:
                dna_seq = parsed[0][1]
        rc_seq = reverse_complement(dna_seq) if mirror_checkbox.value else None
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
        colors = {
            "A": int(helix_color_a.value.lstrip("#"), 16),
            "C": int(helix_color_c.value.lstrip("#"), 16),
            "G": int(helix_color_g.value.lstrip("#"), 16),
            "T": int(helix_color_t.value.lstrip("#"), 16),
        }

        helix_container.controls.append(
            show_helix_ui(
                dna_seq,
                strand2_sequence=rc_seq,
                animate=animate_checkbox.value,
                zoom=zoom_slider.value,
                colors=colors,
                fps=fps_slider.value,
                ws_url="ws://localhost:8765",
            )
        )
        page.update()

    animate_checkbox.on_change = refresh_helix_view
    zoom_slider.on_change = refresh_helix_view
    fps_slider.on_change = refresh_helix_view

    # --- Encode Event Handlers ---
    encode_button.on_click = make_encode_handler(
        page=page,
        selected_encode_input_file_path=selected_encode_input_file_path,
        encode_button=encode_button,
        encode_browse_button=encode_browse_button,
        encode_progress_ring=encode_progress_ring,
        encode_status_text=encode_status_text,
        encode_orig_size_text=encode_orig_size_text,
        encode_dna_len_text=encode_dna_len_text,
        encode_comp_ratio_text=encode_comp_ratio_text,
        encode_bits_per_nt_text=encode_bits_per_nt_text,
        encode_actual_gc_value=encode_actual_gc_value,
        encode_actual_homopolymer_value=encode_actual_homopolymer_value,
        encode_dna_snippet_text=encode_dna_snippet_text,
        fixed_dna_snippet_text=fixed_dna_snippet_text,
        fixed_metrics_text=fixed_metrics_text,
        encode_save_button=encode_save_button,
        encode_manifest_save_button=encode_manifest_save_button,
        encode_hidden_fasta_content=encode_hidden_fasta_content,
        encode_hidden_manifest_content=encode_hidden_manifest_content,
        encode_hidden_sequence=encode_hidden_sequence,
        codeword_hist_image=codeword_hist_image,
        nucleotide_freq_image=nucleotide_freq_image,
        sequence_analysis_plot_image=sequence_analysis_plot_image,
        analysis_status_text=analysis_status_text,
        fix_suggestion_text=fix_suggestion_text,
        app_tabs=app_tabs,
        method_dropdown=method_dropdown,
        parity_checkbox=parity_checkbox,
        k_value_input=k_value_input,
        fec_dropdown=fec_dropdown,
        window_size_input=window_size_input,
        step_size_input=step_size_input,
        min_homopolymer_input=min_homopolymer_input,
        alphabet_dropdown=alphabet_dropdown,
        mirror_checkbox=mirror_checkbox,
        refresh_helix_view=refresh_helix_view,
    )

    async def apply_fix(_: ft.ControlEvent) -> None:
        seq = encode_hidden_sequence.value
        if not seq:
            fixed_metrics_text.value = "No sequence available to fix."
            fixed_dna_snippet_text.value = ""
            page.update()
            return
        constraints = SynthesisConstraints()
        fixed = fix_sequence(
            seq,
            target_gc_min=0.4,
            target_gc_max=0.6,
            max_homopolymer=constraints.max_homopolymer,
        )
        fixed_dna_snippet_text.value = fixed[:200]
        gc_val = calculate_gc_content(fixed)
        hp_len = get_max_homopolymer_length(fixed)
        fixed_metrics_text.value = f"Fixed GC {gc_val:.2%}, max HP {hp_len}"
        page.update()

    fix_button.on_click = apply_fix

    async def on_encode_save_file_result(e: ft.FilePickerResultEvent) -> None:  # Made async for consistency, though not strictly needed here

        if e.path:
            try:
                with open(e.path, "w", encoding="utf-8") as f_out:
                    f_out.write(encode_hidden_fasta_content.value)
                encode_status_text.value = (
                    f"Encoded file saved successfully to: {e.path}"
                )
                encode_status_text.color =  colors.GREEN_700
            except OSError as ex:
                encode_status_text.value = f"Error saving file: {ex}"
                encode_status_text.color =  colors.RED_ACCENT_700
            except Exception as ex:
                logger.exception("Unexpected error while saving encoded FASTA")
                encode_status_text.value = f"Unexpected error saving file: {ex}"
                encode_status_text.color =  colors.RED_ACCENT_700
                raise
        else:
            encode_status_text.value = "Save operation cancelled by user."
            encode_status_text.color =  colors.AMBER_ACCENT_700
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
                encode_status_text.color =  colors.GREEN_700
            except OSError as ex:
                encode_status_text.value = f"Error saving manifest: {ex}"
                encode_status_text.color =  colors.RED_ACCENT_700
            except Exception as ex:
                logger.exception("Unexpected error while saving manifest")
                encode_status_text.value = f"Unexpected error saving manifest: {ex}"
                encode_status_text.color =  colors.RED_ACCENT_700
                raise
        else:
            encode_status_text.value = "Save operation cancelled by user."
            encode_status_text.color =  colors.AMBER_ACCENT_700
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
        "", selectable=True, color= colors.BLUE_GREY_500
    )  # Displays FEC correction/error counts
    decode_progress_ring: ft.ProgressRing = ft.ProgressRing(
        visible=False, width=20, height=20
    )  # Progress indicator

    decode_save_button: ft.ElevatedButton = ft.ElevatedButton(
        "Save Decoded File...", icon=getattr(icons, "SAVE", None), visible=False
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
        icon=getattr(icons, "FOLDER_OPEN", None),
        on_click=_open_decode_file_picker,
    )

    decode_button.on_click = make_decode_handler(
        page=page,
        selected_decode_input_file_path=selected_decode_input_file_path,
        decode_button=decode_button,
        decode_browse_button=decode_browse_button,
        decode_progress_ring=decode_progress_ring,
        decode_status_text=decode_status_text,
        decode_fec_info_text=decode_fec_info_text,
        decode_save_button=decode_save_button,
        decode_alphabet_dropdown=decode_alphabet_dropdown,
    )

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
                decode_status_text.color =  colors.RED_ACCENT_700
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
            ft.Row(
                [
                    ft.Text("Sequence "),
                    glossary_modal_text(
                        "GC content", page, GLOSSARY, GLOSSARY_FULL
                    ),
                    ft.Text(" & "),
                    glossary_modal_text(
                        "Homopolymer", page, GLOSSARY, GLOSSARY_FULL
                    ),
                    ft.Text(" Analysis:"),
                ],
                spacing=0,
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
            ft.ElevatedButton(
                "Open Web Dashboard",
                on_click=lambda _: webbrowser.open(
                    "http://localhost:8000/dashboard"
                ),
            ),
        ],
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
    )

    # --- Main App Structure (Tabs) ---
    # Analysis tab needs to be referenced later to enable/disable
    analysis_tab: ft.Tab = ft.Tab(
        text="Analysis",
        icon=getattr(icons, "ANALYTICS_OUTLINED", None),
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
                icon=getattr(icons, "SEND_AND_ARCHIVE_OUTLINED", None),
                content=ft.Container(
                    ft.Column(
                        controls=[
                            ft.Row(
                                [encode_browse_button, encode_selected_input_file_text]
                            ),
                            encode_drop_zone if encode_drop_zone else ft.Container(),
                            method_dropdown,
                            alphabet_dropdown,
                            ft.Row([parity_checkbox, k_value_input]),
                            fec_dropdown,
                            mirror_checkbox,
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
                            fix_suggestion_text,
                            fix_button,
                            fixed_metrics_text,
                            fixed_dna_snippet_text,
                            encode_hidden_fasta_content,
                            encode_hidden_manifest_content,
                            encode_hidden_sequence,
                        ],
                        spacing=15,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    padding=10,
                    alignment=getattr(ft.alignment, "TOP_LEFT", ft.alignment.top_left),
                ),
            ),
            ft.Tab(
                text="Decode",
                icon=getattr(icons, "UNARCHIVE_OUTLINED", None),
                content=ft.Container(
                    decode_tab_content_column,
                    padding=10,
                    alignment=ft.alignment.top_left,
                ),
            ),
            #(analysis tab defined above to allow setting disabled after init)
            analysis_tab,
            ft.Tab(
                text="Visualizer",
                icon=getattr(icons, "DNA", None),
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


    def on_tab_change(e: ft.ControlEvent) -> None:
        if app_tabs.selected_index == 3:
            refresh_helix_view()


        page.update()

    app_tabs.on_change = on_tab_change

    page.add(app_tabs)  # Add tabs to page first
    page.update()


if __name__ == "__main__":
    ft.app(target=main)
