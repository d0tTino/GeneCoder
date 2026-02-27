import asyncio
import base64 # For displaying matplotlib plots in Flet
import json
import os
import re # For parsing header parameters

import flet as ft

# Project module imports
from genecoder.encoders import calculate_gc_content, get_max_homopolymer_length
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T
from genecoder.formats import to_fasta, from_fasta
from genecoder.pipeline import DecodeRequest, EncodeRequest, GeneCoderPipeline
from genecoder.plotting import (
    prepare_huffman_codeword_length_data,
    generate_codeword_length_histogram,
    prepare_nucleotide_frequency_data,
    generate_nucleotide_frequency_plot,
    calculate_windowed_gc_content,  # New import
    identify_homopolymer_regions,  # New import
    generate_sequence_analysis_plot # New import
)

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

    fec_checkbox = ft.Checkbox(
        label="Enable Triple-Repeat FEC",
        value=False
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
        global decoded_bytes_to_save
        decoded_bytes_to_save = b""

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
            add_parity_encode = parity_checkbox.value
            apply_fec_encode = fec_checkbox.value
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

            with open(input_path, 'rb') as f_in:
                input_data = await asyncio.to_thread(f_in.read)

            method_key = method.lower().replace(' ', '_').replace('-', '_')
            pipeline = GeneCoderPipeline()
            stage_result = await asyncio.to_thread(
                pipeline.run_encode,
                EncodeRequest(
                    data=input_data,
                    method=method_key,
                    add_parity=add_parity_encode and method != "GC-Balanced",
                    k_value=k_val_encode,
                    parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
                    pre_transform='none',
                    channel='triple_repeat' if apply_fec_encode else 'none',
                ),
            )
            raw_dna_sequence = stage_result.encoded_dna
            final_encoded_dna = stage_result.channel_output_dna
            huffman_table_for_header = stage_result.metadata.get('huffman_table', {})
            num_padding_bits_for_header = stage_result.metadata.get('huffman_padding', 0)

            header_parts = [f"method={method_key}", f"input_file={os.path.basename(input_path)}"]
            if add_parity_encode and method != "GC-Balanced":
                header_parts.extend([f"parity_k={k_val_encode}", f"parity_rule={PARITY_RULE_GC_EVEN_A_ODD_T}"])
            if method == "Huffman":
                serializable_table = {str(k): v for k, v in huffman_table_for_header.items()}
                huffman_params = {"table": serializable_table, "padding": num_padding_bits_for_header}
                header_parts.append(f"huffman_params={json.dumps(huffman_params)}")
            elif method == "GC-Balanced":
                header_parts.extend(["gc_min=0.45", "gc_max=0.55", "max_homopolymer=3"])

            if apply_fec_encode:
                header_parts.append("fec=triple_repeat")
                current_status = encode_status_text.value
                encode_status_text.value = (current_status + " ").strip() + "Triple-Repeat FEC applied."
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
                gc_payload = raw_dna_sequence[1:] if len(raw_dna_sequence) > 0 else ""
                actual_gc = await asyncio.to_thread(calculate_gc_content, gc_payload)
                encode_actual_gc_text.value = f"Actual GC content (payload, pre-FEC): {actual_gc:.2%}"
                actual_max_hp = await asyncio.to_thread(get_max_homopolymer_length, gc_payload)
                encode_actual_homopolymer_text.value = f"Actual max homopolymer (payload, pre-FEC): {actual_max_hp}"
            else:
                encode_actual_gc_text.value = "Actual GC content (payload): N/A"
                encode_actual_homopolymer_text.value = "Actual max homopolymer (payload): N/A"

            encode_dna_snippet_text.value = final_encoded_dna[:200]
            encode_save_button.visible = True
            
            base_success_msg = "Encoding successful! Click 'Save Encoded FASTA...' to save."
            if apply_fec_encode and "Triple-Repeat FEC applied" in encode_status_text.value :
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
                except Exception as plot_ex: current_analysis_status_messages.append(f"Huffman plot error: {plot_ex}")
            else: current_analysis_status_messages.append("Codeword histogram for Huffman only.")
            
            if final_encoded_dna: # Use final_encoded_dna for nucleotide frequency
                try:
                    nucleotide_counts = await asyncio.to_thread(prepare_nucleotide_frequency_data, final_encoded_dna)
                    if any(nucleotide_counts.values()):
                        freq_buf = await asyncio.to_thread(generate_nucleotide_frequency_plot, nucleotide_counts)
                        nucleotide_freq_image.src_base64 = base64.b64encode(freq_buf.getvalue()).decode('utf-8')
                        freq_buf.close()
                        analysis_tab_is_enabled = True
                except Exception as plot_ex: current_analysis_status_messages.append(f"Nucleotide plot error: {plot_ex}")
            else: current_analysis_status_messages.append("Empty sequence for nucleotide plot.")

            # Generate and display new sequence analysis plot
            sequence_analysis_plot_image.src_base64 = None
            if final_encoded_dna: # Use final_encoded_dna for this plot as well
                try:
                    window_size = 50 
                    step = 10
                    min_homopolymer_len = 4 # Default min length for homopolymer display
                    
                    gc_data = await asyncio.to_thread(
                        calculate_windowed_gc_content, final_encoded_dna, window_size, step
                    )
                    homopolymer_data = await asyncio.to_thread(
                        identify_homopolymer_regions, final_encoded_dna, min_homopolymer_len
                    )
                    
                    # Check if gc_data or homopolymer_data has meaningful content before plotting
                    # generate_sequence_analysis_plot should handle empty inputs, but good to be defensive
                    if (gc_data and gc_data[0]) or homopolymer_data : # Check if there's any data to plot
                        plot_buf = await asyncio.to_thread(
                            generate_sequence_analysis_plot, gc_data, homopolymer_data, len(final_encoded_dna)
                        )
                        sequence_analysis_plot_image.src_base64 = base64.b64encode(plot_buf.getvalue()).decode('utf-8')
                        plot_buf.close()
                        analysis_tab_is_enabled = True # Enable tab if this plot is generated
                        current_analysis_status_messages.append("Sequence analysis plot generated.")
                    else:
                        current_analysis_status_messages.append("No significant data for sequence analysis plot (GC/Homopolymers).")
                        
                except Exception as plot_ex:
                    current_analysis_status_messages.append(f"Sequence analysis plot error: {plot_ex}")
                    sequence_analysis_plot_image.src_base64 = None
            else:
                current_analysis_status_messages.append("Empty sequence for sequence analysis plot.")

            
            final_analysis_status = " | ".join(msg for msg in current_analysis_status_messages if msg and msg.strip()).strip()
            if not final_analysis_status and analysis_tab_is_enabled : 
                 analysis_status_text.value = "All analysis plots generated successfully."
                 analysis_status_text.color = ft.colors.GREEN_700
            elif not analysis_tab_is_enabled and not final_analysis_status : 
                 analysis_status_text.value = "No analysis plots applicable or generated for the selected options."
                 analysis_status_text.color = ft.colors.ORANGE_ACCENT_700 # Or some neutral info color
            else: 
                analysis_status_text.value = final_analysis_status
                # Determine overall color based on presence of "error" or "warning" keywords
                if "error" in final_analysis_status.lower():
                    analysis_status_text.color = ft.colors.RED_ACCENT_700
                elif "warning" in final_analysis_status.lower() or "empty" in final_analysis_status.lower() or "no significant data" in final_analysis_status.lower():
                    analysis_status_text.color = ft.colors.ORANGE_ACCENT_700
                else: # Success or partial success messages
                    analysis_status_text.color = ft.colors.GREEN_700 if "generated" in final_analysis_status else ft.colors.BLUE_GREY_400


            if len(app_tabs.tabs) > 2: app_tabs.tabs[2].disabled = not analysis_tab_is_enabled

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

    encode_tab_content_column = ft.Column(
        controls=[
            ft.Row([encode_browse_button, encode_selected_input_file_text], alignment=ft.MainAxisAlignment.START),
            method_dropdown,
            ft.Row([parity_checkbox, k_value_input]),
            fec_checkbox, # Added FEC checkbox
            encode_button,
            ft.Divider(),
            ft.Text("Metrics:", weight=ft.FontWeight.BOLD),
            encode_orig_size_text,
            encode_dna_len_text,
            encode_comp_ratio_text,
            encode_bits_per_nt_text,
            encode_actual_gc_text,
            encode_actual_homopolymer_text, # Added here
            ft.Text("Output Preview:", weight=ft.FontWeight.BOLD),
            encode_dna_snippet_text,
            encode_save_button,
            encode_status_text,
            encode_hidden_fasta_content, # Hidden field for storing full FASTA
        ],
        spacing=15,
        scroll=ft.ScrollMode.AUTO,
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
    decode_button = ft.ElevatedButton("Decode")

    async def decode_file_data(e): # Corrected from 'def' to 'async def' in my thoughts, already async in code
        """
        Handles the decoding process when the 'Decode' button is clicked.
        
        This asynchronous function performs the following steps:
        1. Disables UI controls (buttons, progress ring) to prevent concurrent operations.
        2. Resets UI elements (status texts).
        3. Validates input file selection.
        4. Reads FASTA file content asynchronously.
        5. Parses FASTA records.
        6. If Triple-Repeat FEC is indicated in the header, applies FEC decoding 
           asynchronously and updates `decode_fec_info_text`. Handles sequence length validation for FEC.
        7. Determines the primary decoding method from the FASTA header.
        8. Parses method-specific parameters (e.g., Huffman table, GC constraints, parity) from the header.
        9. Applies the primary decoding method asynchronously.
        10. Updates status messages and re-enables UI controls in a `finally` block.
        """
        global decoded_bytes_to_save 
        
        decode_status_text.value = "Processing..."
        decode_fec_info_text.value = "" 
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

            with open(input_path, 'r', encoding='utf-8') as f_in:
                file_content_str = await asyncio.to_thread(f_in.read)

            parsed_records = await asyncio.to_thread(from_fasta, file_content_str)
            if not parsed_records:
                decode_status_text.value = f"Error: No valid FASTA records found in '{os.path.basename(input_path)}'."
                decode_status_text.color = ft.colors.RED_ACCENT_700
                page.update()
                return
            
            current_decode_status_messages = []
            if len(parsed_records) > 1:
                current_decode_status_messages.append("Warning: Multiple FASTA records; processing first one.")

            header, sequence_from_fasta = parsed_records[0]
            
            pre_transform = 'hamming_7_4' if "fec=hamming_7_4" in header else 'none'
            channel = 'triple_repeat' if "fec=triple_repeat" in header else 'none'
            if channel == 'triple_repeat':
                current_decode_status_messages.append("Triple-Repeat FEC detected.")

            detected_method_str = None
            huffman_table = None
            num_padding_bits = 0
            check_parity = False
            k_val_decode = 7

            if "method=huffman" in header and "huffman_params={" in header:
                detected_method_str = "huffman"
                json_param_field_start = header.find("huffman_params=")
                json_part_with_key = header[json_param_field_start + len("huffman_params="):]
                first_bracket_index = json_part_with_key.find('{')
                open_brackets = 0
                json_end_index = -1
                for i, char_h in enumerate(json_part_with_key[first_bracket_index:]):
                    if char_h == '{':
                        open_brackets += 1
                    elif char_h == '}':
                        open_brackets -= 1
                    if open_brackets == 0:
                        json_end_index = first_bracket_index + i + 1
                        break
                huffman_params = json.loads(json_part_with_key[first_bracket_index:json_end_index])
                huffman_table = {int(k): v for k, v in huffman_params.get('table', {}).items()}
                num_padding_bits = huffman_params.get('padding', 0)
            elif "method=base4_direct" in header:
                detected_method_str = "base4_direct"
            elif "method=gc_balanced" in header:
                detected_method_str = "gc_balanced"

            if detected_method_str is None:
                decode_status_text.value = "Error: Could not determine decoding method."
                decode_status_text.color = ft.colors.RED_ACCENT_700
                page.update()
                return

            if detected_method_str != "gc_balanced" and "parity_k=" in header and "parity_rule=" in header:
                check_parity = True
                k_val_decode = int(header.split("parity_k=")[1].split()[0])

            gc_min_match = re.search(r"gc_min=([\d.]+)", header)
            gc_max_match = re.search(r"gc_max=([\d.]+)", header)
            max_homopolymer_match = re.search(r"max_homopolymer=(\d+)", header)
            fec_padding_match = re.search(r"fec_padding_bits=(\d+)", header)

            pipeline = GeneCoderPipeline()
            decode_stage_result = await asyncio.to_thread(
                pipeline.run_decode,
                DecodeRequest(
                    dna_sequence=sequence_from_fasta,
                    method=detected_method_str,
                    check_parity=check_parity,
                    k_value=k_val_decode,
                    parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
                    pre_transform=pre_transform,
                    channel=channel,
                    huffman_table=huffman_table,
                    huffman_padding=num_padding_bits,
                    gc_min=float(gc_min_match.group(1)) if gc_min_match else None,
                    gc_max=float(gc_max_match.group(1)) if gc_max_match else None,
                    max_homopolymer=int(max_homopolymer_match.group(1)) if max_homopolymer_match else None,
                    pre_transform_padding_bits=int(fec_padding_match.group(1)) if fec_padding_match else 0,
                ),
            )
            decoded_bytes_result = decode_stage_result.decoded_bytes or decode_stage_result.transformed_bytes
            parity_errors = decode_stage_result.parity_errors

            if channel == 'triple_repeat':
                corrected = decode_stage_result.metadata.get('channel_corrected', 0)
                uncorrectable = decode_stage_result.metadata.get('channel_uncorrectable', 0)
                decode_fec_info_text.value = f"Triple-Repeat FEC: {corrected} corrected, {uncorrectable} uncorrectable."
            else:
                decode_fec_info_text.value = "No FEC detected in header."
            page.update()

            decoded_bytes_to_save = decoded_bytes_result
            final_status_message = " ".join(current_decode_status_messages) + " Decoding successful."
            if check_parity and parity_errors and detected_method_str != "gc_balanced":
                final_status_message += f" Parity error(s) at blocks: {parity_errors}."
                decode_status_text.color = ft.colors.AMBER_ACCENT_700
            else: decode_status_text.color = ft.colors.GREEN_700
            decode_status_text.value = final_status_message
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

    async def on_save_decoded_file_result(e: ft.FilePickerResultEvent): # Made async
        global decoded_bytes_to_save
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
                            fec_checkbox,
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
