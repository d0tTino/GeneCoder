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
"""

import flet as ft
import os
import asyncio  # For asynchronous operations

# Project module imports
from genecoder import (
    EncodeOptions,
    perform_encoding,
    perform_decoding,
)
from .flet_helpers import parse_int_input

encode_fasta_data_to_save_ref = ft.Ref[str]()
decoded_bytes_to_save: bytes = b"" 

def main(page: ft.Page):
    page.title = "GeneCoder"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    
    selected_encode_input_file_path = ft.Ref[str]() 
    selected_encode_input_file_path.current = "" 

    selected_decode_input_file_path = ft.Ref[str]() 
    selected_decode_input_file_path.current = ""

    # --- Analysis Tab UI Controls (defined early for access in encode_data) ---
    codeword_hist_image = ft.Image(
        width=500, height=350, fit=ft.ImageFit.CONTAIN, 
        tooltip="Huffman Codeword Length Histogram"
    )
    nucleotide_freq_image = ft.Image(
        width=500, height=350, fit=ft.ImageFit.CONTAIN, 
        tooltip="Nucleotide Frequency Distribution"
    )
    sequence_analysis_plot_image = ft.Image( # New image control
        width=600, height=400, fit=ft.ImageFit.CONTAIN,
        tooltip="Sequence GC & Homopolymer Analysis"
    )
    analysis_status_text = ft.Text("Encode data to view analysis plots.", italic=True)

    window_size_input = ft.TextField(
        label="GC Window Size",
        value="50",
        width=120,
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    step_size_input = ft.TextField(
        label="Step",
        value="10",
        width=100,
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    min_homopolymer_input = ft.TextField(
        label="Min Homopolymer Length",
        value="4",
        width=180,
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    # --- Encode Tab UI Controls ---
    encode_selected_input_file_text = ft.Text("No file selected.", italic=True)
    
    def on_encode_file_picker_result(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            selected_encode_input_file_path.current = e.files[0].path
            encode_selected_input_file_text.value = f"Selected: {os.path.basename(e.files[0].name)}"
        else:
            selected_encode_input_file_path.current = ""
            encode_selected_input_file_text.value = "File selection cancelled or failed."
        page.update()

    encode_file_picker = ft.FilePicker(on_result=on_encode_file_picker_result)
    page.overlay.append(encode_file_picker) 

    encode_browse_button = ft.ElevatedButton(
        "Browse File",
        icon=ft.icons.FOLDER_OPEN,
        on_click=lambda _: encode_file_picker.pick_files(
            allow_multiple=False,
            dialog_title="Select Input File for Encoding"
        )
    )

    method_dropdown = ft.Dropdown(
        label="Encoding Method",
        options=[
            ft.dropdown.Option("Base-4 Direct"),
            ft.dropdown.Option("Huffman"),
            ft.dropdown.Option("GC-Balanced"),
        ],
        value="Base-4 Direct"
    )

    k_value_input = ft.TextField(
        label="k-value (for parity)", 
        value="7", 
        width=150, 
        disabled=True, 
        keyboard_type=ft.KeyboardType.NUMBER
    )

    parity_checkbox = ft.Checkbox(
        label="Add Parity",
        value=False,
        on_change=lambda e: setattr(k_value_input, 'disabled', not e.control.value) or page.update()
    )

    def on_fec_change(e: ft.ControlEvent):
        if e.control.value == "Hamming(7,4)":

            parity_checkbox.disabled = True
            k_value_input.disabled = True
        else:
            parity_checkbox.disabled = False
            k_value_input.disabled = not parity_checkbox.value
        page.update()

    fec_dropdown = ft.Dropdown(
        label="FEC Method",
        options=[
            ft.dropdown.Option("None"),
            ft.dropdown.Option("Triple-Repeat"),
            ft.dropdown.Option("Hamming(7,4)"),
        ],
        value="None",
        on_change=on_fec_change,
    )

    fec_info_text = ft.Text(
        "Add Parity is disabled when Hamming(7,4) is selected.",
        size=12,

        italic=True,
    )
    
    encode_button = ft.ElevatedButton("Encode")

    encode_status_text = ft.Text("", selectable=True)
    encode_orig_size_text = ft.Text("Original size: - bytes")
    encode_dna_len_text = ft.Text("Encoded DNA length: - nucleotides")
    encode_comp_ratio_text = ft.Text("Compression ratio: -")
    encode_bits_per_nt_text = ft.Text("Bits per nucleotide: - bits/nt")
    encode_actual_gc_text = ft.Text("Actual GC content (payload): -")
    encode_actual_homopolymer_text = ft.Text("Actual max homopolymer (payload): -")
    encode_progress_ring = ft.ProgressRing(visible=False, width=20, height=20) # Progress indicator
    
    encode_dna_snippet_text = ft.TextField(
        label="DNA Snippet (first 200 chars)",
        read_only=True, 
        multiline=True, 
        max_lines=3,
        value="",
        width=500 
    )

    encode_save_button = ft.ElevatedButton(
        "Save Encoded FASTA...", 
        icon=ft.icons.SAVE,
        visible=False 
    )
    
    encode_hidden_fasta_content = ft.Text(ref=encode_fasta_data_to_save_ref, visible=False, value="")

    # --- Main App Structure (Tabs) defined here so encode_data can access app_tabs.tabs[2] ---
    # This is a forward declaration of sorts for app_tabs, its full definition with content is later.
    app_tabs = ft.Tabs() 

    # --- Encode Event Handlers ---
    async def encode_data(e):
        """
        Handles the encoding process when the 'Encode' button is clicked.
        
        This asynchronous function performs the following steps:
        1. Disables UI controls (buttons, progress ring) to prevent concurrent operations.
        2. Resets UI elements (status texts, image displays).
        3. Validates user inputs (file selection, parity k-value).
        4. Reads input file data asynchronously.
        5. Applies the selected encoding method (Base-4 Direct, Huffman, GC-Balanced) 
           asynchronously using `asyncio.to_thread`.
        6. Optionally applies Triple-Repeat FEC if selected, also asynchronously.
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
        encode_hidden_fasta_content.value = ""
        
        codeword_hist_image.src_base64 = None
        nucleotide_freq_image.src_base64 = None
        sequence_analysis_plot_image.src_base64 = None # Clear new plot
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

            method = method_dropdown.value
            fec_method = fec_dropdown.value
            add_parity_encode = parity_checkbox.value and fec_method != "Hamming(7,4)"

            k_val_encode = 7
            if add_parity_encode:
                if not k_value_input.value:
                    encode_status_text.value = "Error: Parity k-value cannot be empty."
                    encode_status_text.color = ft.colors.RED_ACCENT_700
                    page.update()
                    return
                try:
                    k_val_encode = int(k_value_input.value)
                    if k_val_encode <= 0:
                        encode_status_text.value = "Error: Parity k-value must be positive."
                        encode_status_text.color = ft.colors.RED_ACCENT_700
                        page.update()
                        return
                except ValueError:
                    encode_status_text.value = "Error: Parity k-value must be an integer."
                    encode_status_text.color = ft.colors.RED_ACCENT_700
                    page.update()
                    return

            if method == "GC-Balanced" and add_parity_encode:
                encode_status_text.value = "Info: 'Add Parity' not directly used by GC-Balanced."

            with open(input_path, "rb") as f_in:
                input_data = await asyncio.to_thread(f_in.read)

            window_size = parse_int_input(window_size_input.value, 50, 1)
            step = parse_int_input(step_size_input.value, 10, 1)
            min_hp = parse_int_input(min_homopolymer_input.value, 4, 2)

            options = EncodeOptions(
                method=method,
                add_parity=add_parity_encode,
                k_value=k_val_encode,
                fec_method=fec_method,
                window_size=window_size,
                step_size=step,
                min_homopolymer_len=min_hp,
            )

            result = await asyncio.to_thread(perform_encoding, input_data, options)

            encode_hidden_fasta_content.value = result.fasta

            encode_orig_size_text.value = f"Original size: {result.metrics['original_size']} bytes"
            encode_dna_len_text.value = (
                f"Encoded DNA length: {result.metrics['dna_length']} nucleotides (Post-FEC)"
            )
            encode_comp_ratio_text.value = f"Compression ratio: {result.metrics['compression_ratio']:.2f}"
            encode_bits_per_nt_text.value = (
                f"Bits per nucleotide: {result.metrics['bits_per_nt']:.2f} bits/nt"
            )

            header_parts = [f"method={method.lower().replace(' ', '_').replace('-', '_')}", f"input_file={os.path.basename(input_path)}"]
            if add_parity_encode and method != "GC-Balanced":
                header_parts.extend([f"parity_k={k_val_encode}", f"parity_rule={PARITY_RULE_GC_EVEN_A_ODD_T}"])
            if method == "Huffman":
                serializable_table = {str(k): v for k, v in huffman_table_for_header.items()}
                huffman_params = {"table": serializable_table, "padding": num_padding_bits_for_header}
                header_parts.append(f"huffman_params={json.dumps(huffman_params)}")
            elif method == "GC-Balanced":
                header_parts.extend([f"gc_min={target_gc_min}", f"gc_max={target_gc_max}", f"max_homopolymer={max_homopolymer}"])

            final_encoded_dna = raw_dna_sequence
            if fec_method == "Triple-Repeat":
                final_encoded_dna = await asyncio.to_thread(encode_triple_repeat, raw_dna_sequence)
                header_parts.append("fec=triple_repeat")
                # Append to status text; ensure it's not overwritten if already an info message
                current_status = encode_status_text.value
                if "Info:" in current_status:  # If there's already an info message (like GC-Balanced + Parity)
                    encode_status_text.value = current_status + " Triple-Repeat FEC applied."
                else:
                    # Otherwise, set it directly or append to a success message later
                    encode_status_text.value = "Triple-Repeat FEC applied."  # This might get overwritten by "Encoding successful"
                encode_status_text.color = ft.colors.BLUE_GREY_400
            
            fasta_header = " ".join(header_parts)
            final_fasta_str = await asyncio.to_thread(to_fasta, final_encoded_dna, fasta_header, 80)
            encode_hidden_fasta_content.value = final_fasta_str

            original_size_bytes = len(input_data)
            final_encoded_length_nucleotides = len(final_encoded_dna)
            dna_equivalent_bytes = final_encoded_length_nucleotides * 0.25
            compression_ratio = original_size_bytes / dna_equivalent_bytes if dna_equivalent_bytes > 0 else (float('inf') if original_size_bytes > 0 else 0.0)
            bits_per_nt_val = (original_size_bytes * 8) / final_encoded_length_nucleotides if final_encoded_length_nucleotides != 0 else 0.0

            encode_orig_size_text.value = f"Original size: {original_size_bytes} bytes"
            encode_dna_len_text.value = f"Encoded DNA length: {final_encoded_length_nucleotides} nucleotides (Post-FEC)"
            encode_comp_ratio_text.value = f"Compression ratio: {compression_ratio:.2f}"
            encode_bits_per_nt_text.value = f"Bits per nucleotide: {bits_per_nt_val:.2f} bits/nt"
            
            if method == "GC-Balanced":
                encode_actual_gc_text.value = (
                    f"Actual GC content (payload, pre-FEC): {result.metrics['actual_gc']:.2%}"
                )
                encode_actual_homopolymer_text.value = (
                    f"Actual max homopolymer (payload, pre-FEC): {result.metrics['max_homopolymer']}"
                )
            else:
                encode_actual_gc_text.value = "Actual GC content (payload): N/A"
                encode_actual_homopolymer_text.value = "Actual max homopolymer (payload): N/A"

            encode_dna_snippet_text.value = result.encoded_dna[:200]
            encode_save_button.visible = True
            
            base_success_msg = "Encoding successful! Click 'Save Encoded FASTA...' to save."
            if fec_method == "Triple-Repeat" and "Triple-Repeat FEC applied" in encode_status_text.value :
                if "Info:" in encode_status_text.value: # If there was GC-Balanced + Parity warning
                     encode_status_text.value = encode_status_text.value.replace("Triple-Repeat FEC applied.", base_success_msg + " Triple-Repeat FEC applied.")
                else: # Just FEC applied
                     encode_status_text.value = base_success_msg + " Triple-Repeat FEC applied."
            elif "Info:" not in encode_status_text.value : # No prior info messages
                 encode_status_text.value = base_success_msg
            # If "Info:" was there but no FEC, it remains.
            
            encode_status_text.color = ft.colors.GREEN_700 # Assume success if no error thrown

            analysis_tab_is_enabled = False
            current_analysis_status_messages = []

            if method == "Huffman" and huffman_table_for_header:
                try:
                    length_counts = await asyncio.to_thread(prepare_huffman_codeword_length_data, huffman_table_for_header)
                    if any(length_counts.values()):
                        hist_buf = await asyncio.to_thread(generate_codeword_length_histogram, length_counts)
                        codeword_hist_image.src_base64 = base64.b64encode(hist_buf.getvalue()).decode('utf-8')
                        hist_buf.close()
                        analysis_tab_is_enabled = True
                except Exception as plot_ex:
                    current_analysis_status_messages.append(f"Huffman plot error: {plot_ex}")
            else:
                current_analysis_status_messages.append("Codeword histogram for Huffman only.")
            
            if final_encoded_dna: # Use final_encoded_dna for nucleotide frequency
                try:
                    nucleotide_counts = await asyncio.to_thread(prepare_nucleotide_frequency_data, final_encoded_dna)
                    if any(nucleotide_counts.values()):
                        freq_buf = await asyncio.to_thread(generate_nucleotide_frequency_plot, nucleotide_counts)
                        nucleotide_freq_image.src_base64 = base64.b64encode(freq_buf.getvalue()).decode('utf-8')
                        freq_buf.close()
                        analysis_tab_is_enabled = True
                except Exception as plot_ex:
                    current_analysis_status_messages.append(f"Nucleotide plot error: {plot_ex}")
            else:
                current_analysis_status_messages.append("Empty sequence for nucleotide plot.")


            status_prefix = " ".join(result.info_messages)
            encode_status_text.value = (
                (status_prefix + " " if status_prefix else "")
                + "Encoding successful! Click 'Save Encoded FASTA...' to save."
            )
            encode_status_text.color = ft.colors.GREEN_700

            codeword_hist_image.src_base64 = result.plots.get("codeword_hist")
            nucleotide_freq_image.src_base64 = result.plots.get("nucleotide_freq")
            sequence_analysis_plot_image.src_base64 = result.plots.get("sequence_analysis")

            any_plot = any(result.plots.values())
            if any_plot:
                analysis_status_text.value = "All analysis plots generated successfully."
                analysis_status_text.color = ft.colors.GREEN_700
            else:
                analysis_status_text.value = "No analysis plots applicable or generated for the selected options."
                analysis_status_text.color = ft.colors.ORANGE_ACCENT_700
            if len(app_tabs.tabs) > 2:
                app_tabs.tabs[2].disabled = not any_plot

        except FileNotFoundError:
            encode_status_text.value = f"Error: Input file '{input_path}' not found."
            encode_status_text.color = ft.colors.RED_ACCENT_700
        except Exception as ex:
            encode_status_text.value = f"An error occurred during encoding: {ex}"
            encode_status_text.color = ft.colors.RED_ACCENT_700
        finally:
            # Re-enable buttons and hide progress
            encode_button.disabled = False
            encode_browse_button.disabled = False
            encode_progress_ring.visible = False
            page.update()

    encode_button.on_click = encode_data

    async def on_encode_save_file_result(e: ft.FilePickerResultEvent): # Made async for consistency, though not strictly needed here
        if e.path:
            try:
                with open(e.path, "w", encoding="utf-8") as f_out:
                    f_out.write(encode_hidden_fasta_content.value) 
                encode_status_text.value = f"Encoded file saved successfully to: {e.path}"
                encode_status_text.color = ft.colors.GREEN_700
            except Exception as ex:
                encode_status_text.value = f"Error saving file: {ex}"
                encode_status_text.color = ft.colors.RED_ACCENT_700
        else:
            encode_status_text.value = "Save operation cancelled by user."
            encode_status_text.color = ft.colors.AMBER_ACCENT_700
        page.update()

    encode_save_file_picker = ft.FilePicker(on_result=on_encode_save_file_result)
    page.overlay.append(encode_save_file_picker)

    encode_save_button.on_click = lambda _: encode_save_file_picker.save_file(
        dialog_title="Save Encoded FASTA File",
        file_name="encoded_output.fasta",
        allowed_extensions=["fasta", "fa"]
    )


    # --- Decode Tab UI Controls & Logic ---
    decode_selected_input_file_text = ft.Text("No FASTA file selected.", italic=True)
    decode_status_text = ft.Text("", selectable=True) # Main status for decoding results
    decode_fec_info_text = ft.Text("", selectable=True, color=ft.colors.BLUE_GREY_500) # Displays FEC correction/error counts
    decode_progress_ring = ft.ProgressRing(visible=False, width=20, height=20) # Progress indicator

    decode_save_button = ft.ElevatedButton(
        "Save Decoded File...",
        icon=ft.icons.SAVE,
        visible=False
    )

    decode_button = ft.ElevatedButton("Decode")

    decode_stream_checkbox = ft.Checkbox(label="Stream large files", value=False)

    async def on_decode_file_picker_result(e: ft.FilePickerResultEvent): # Made async
        if e.files and len(e.files) > 0:
            selected_decode_input_file_path.current = e.files[0].path
            decode_selected_input_file_text.value = f"Selected: {os.path.basename(e.files[0].name)}"
        else:
            selected_decode_input_file_path.current = ""
            decode_selected_input_file_text.value = "File selection cancelled or failed."
        decode_status_text.value = "" 
        decode_save_button.visible = False
        page.update()

    decode_file_picker = ft.FilePicker(on_result=on_decode_file_picker_result)
    page.overlay.append(decode_file_picker)

    decode_browse_button = ft.ElevatedButton(
        "Browse FASTA File",
        icon=ft.icons.FOLDER_OPEN,
        on_click=lambda _: decode_file_picker.pick_files(
            allow_multiple=False,
            dialog_title="Select FASTA File for Decoding",
            allowed_extensions=["fasta", "fa", "txt"] 
        )
    )

    async def decode_file_data(e):
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
                decode_status_text.value = "Error: Please select an input FASTA file first."
                decode_status_text.color = ft.colors.RED_ACCENT_700
                page.update()
                return

            with open(input_path, "r", encoding="utf-8") as f_in:
                file_content_str = await asyncio.to_thread(f_in.read)

            try:
                result = await asyncio.to_thread(perform_decoding, file_content_str)
            except Exception as ex:
                decode_status_text.value = f"Error: {ex}"
                decode_status_text.color = ft.colors.RED_ACCENT_700
                page.update()
                return

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
        except Exception as ex:
            decode_status_text.value = f"An critical error occurred: {ex}"
            decode_status_text.color = ft.colors.RED_ACCENT_700
        finally:
            decode_progress_ring.visible = False
            decode_button.disabled = False
            decode_browse_button.disabled = False
            page.update()

    decode_button.on_click = decode_file_data

    async def on_save_decoded_file_result(e: ft.FilePickerResultEvent):  # Made async
        if e.path:
            try:
                with open(e.path, "wb") as f_out: 
                    f_out.write(decoded_bytes_to_save)
                decode_status_text.value = f"Decoded file saved successfully to {e.path}"
            except Exception as ex:
                decode_status_text.value = f"Error saving decoded file: {ex}"
        else:
            decode_status_text.value = "Save decoded file cancelled."
        page.update()

    save_decoded_file_picker = ft.FilePicker(on_result=on_save_decoded_file_result)
    page.overlay.append(save_decoded_file_picker)

    decode_save_button.on_click = lambda _: save_decoded_file_picker.save_file(
        dialog_title="Save Decoded File",
        file_name="decoded_output.bin" 
    )

    decode_tab_content_column = ft.Column(
        controls=[
            ft.Row([decode_browse_button, decode_selected_input_file_text], alignment=ft.MainAxisAlignment.START),
            ft.Row([decode_button, decode_progress_ring]), # Added progress ring
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
    analysis_tab_content_column = ft.Column(
        controls=[
            analysis_status_text,
            ft.Divider(),
            ft.Text("Huffman Codeword Length Histogram:", weight=ft.FontWeight.BOLD),
            codeword_hist_image,
            ft.Divider(),
            ft.Text("Nucleotide Frequency Distribution (Encoded Sequence):", weight=ft.FontWeight.BOLD),
            nucleotide_freq_image,
            ft.Divider(), # New divider
            ft.Text("Sequence GC & Homopolymer Analysis:", weight=ft.FontWeight.BOLD), # New title
            ft.Row([
                window_size_input,
                step_size_input,
                min_homopolymer_input,
            ], alignment=ft.MainAxisAlignment.START),
            sequence_analysis_plot_image, # New plot image
        ],
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
    )
    
    # --- Main App Structure (Tabs) ---
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
                            ft.Row([encode_browse_button, encode_selected_input_file_text]),
                            method_dropdown,
                            ft.Row([parity_checkbox, k_value_input]),
                            ft.Column([
                                fec_dropdown,
                                fec_info_text,
                            ], spacing=5),

                            ft.Row([encode_button, encode_progress_ring]), # Added progress ring
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
                            encode_status_text,
                            encode_hidden_fasta_content,
                        ],
                        spacing=15, scroll=ft.ScrollMode.AUTO
                    ), padding=10, alignment=ft.alignment.TOP_LEFT
                )
            ),
            ft.Tab(
                text="Decode",
                icon=ft.icons.UNARCHIVE_OUTLINED,
                content=ft.Container(decode_tab_content_column, padding=10, alignment=ft.alignment.top_left)
            ),
            ft.Tab(
                text="Analysis",
                icon=ft.icons.ANALYTICS_OUTLINED,
                content=ft.Container(analysis_tab_content_column, padding=10, alignment=ft.alignment.top_left),
                disabled=True # Initially disabled until data is encoded
            )
        ],
        expand=True
    )

    page.add(app_tabs) # Add tabs to page first
    page.update()


if __name__ == "__main__":
    ft.app(target=main)
