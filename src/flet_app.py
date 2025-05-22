import flet as ft
import os 
import json 
import base64 # For displaying matplotlib plots in Flet

# Project module imports
from genecoder.encoders import encode_base4_direct, decode_base4_direct
from genecoder.huffman_coding import encode_huffman, decode_huffman
from genecoder.formats import to_fasta, from_fasta
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T
from genecoder.plotting import ( 
    prepare_huffman_codeword_length_data,
    generate_codeword_length_histogram,
    prepare_nucleotide_frequency_data,
    generate_nucleotide_frequency_plot
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
    
    encode_button = ft.ElevatedButton("Encode")

    encode_status_text = ft.Text("", selectable=True)
    encode_orig_size_text = ft.Text("Original size: - bytes")
    encode_dna_len_text = ft.Text("Encoded DNA length: - nucleotides")
    encode_comp_ratio_text = ft.Text("Compression ratio: -")
    encode_bits_per_nt_text = ft.Text("Bits per nucleotide: - bits/nt")
    
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
    def encode_data(e):
        nonlocal decoded_bytes_to_save 
        decoded_bytes_to_save = b"" 
        
        encode_status_text.value = "Processing..."
        encode_orig_size_text.value = "Original size: - bytes"
        encode_dna_len_text.value = "Encoded DNA length: - nucleotides"
        encode_comp_ratio_text.value = "Compression ratio: -"
        encode_bits_per_nt_text.value = "Bits per nucleotide: - bits/nt"
        encode_dna_snippet_text.value = ""
        encode_save_button.visible = False
        encode_hidden_fasta_content.value = ""
        
        codeword_hist_image.src_base64 = None
        nucleotide_freq_image.src_base64 = None
        analysis_status_text.value = "Encode data to view analysis plots."
        if len(app_tabs.tabs) > 2: 
            app_tabs.tabs[2].disabled = True
        
        page.update()

        input_path = selected_encode_input_file_path.current
        if not input_path:
            encode_status_text.value = "Error: Please select an input file first."
            encode_status_text.color = ft.colors.RED_ACCENT_700
            page.update()
            return

        method = method_dropdown.value
        add_parity_encode = parity_checkbox.value
        k_val_encode = 7 
        if add_parity_encode:
            if not k_value_input.value: # Check if k_value_input is empty
                encode_status_text.value = "Error: Parity k-value cannot be empty when 'Add Parity' is checked."
                encode_status_text.color = ft.colors.RED_ACCENT_700
                page.update()
                return
            try:
                k_val_encode = int(k_value_input.value)
                if k_val_encode <= 0:
                    encode_status_text.value = "Error: Parity k-value must be a positive integer."
                    encode_status_text.color = ft.colors.RED_ACCENT_700
                    page.update()
                    return
            except ValueError:
                encode_status_text.value = "Error: Parity k-value must be a valid integer."
                encode_status_text.color = ft.colors.RED_ACCENT_700
                page.update()
                return
        
        try:
            with open(input_path, 'rb') as f_in:
                input_data = f_in.read()

            raw_dna_sequence = ""
            huffman_table_for_header = {} 
            num_padding_bits_for_header = 0
            
            if method == "Base-4 Direct":
                raw_dna_sequence = encode_base4_direct(
                    input_data, 
                    add_parity=add_parity_encode, 
                    k_value=k_val_encode, 
                    parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T 
                )
            elif method == "Huffman":
                raw_dna_sequence, huffman_table_for_header, num_padding_bits_for_header = encode_huffman(
                    input_data,
                    add_parity=add_parity_encode,
                    k_value=k_val_encode,
                    parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
                )
            else:
                encode_status_text.value = f"Error: Unknown method '{method}'."
                page.update()
                return

            header_parts = [f"method={method.lower().replace(' ', '_')}", f"input_file={os.path.basename(input_path)}"]
            if add_parity_encode:
                header_parts.append(f"parity_k={k_val_encode}")
                header_parts.append(f"parity_rule={PARITY_RULE_GC_EVEN_A_ODD_T}")

            if method == "Huffman":
                serializable_table = {str(k): v for k, v in huffman_table_for_header.items()}
                huffman_params = {"table": serializable_table, "padding": num_padding_bits_for_header}
                header_parts.append(f"huffman_params={json.dumps(huffman_params)}")
            
            fasta_header = " ".join(header_parts)
            final_fasta_str = to_fasta(raw_dna_sequence, fasta_header, line_width=80)
            encode_hidden_fasta_content.value = final_fasta_str 

            original_size_bytes = len(input_data)
            encoded_dna_length_nucleotides = len(raw_dna_sequence)

            comp_ratio_denom = encoded_dna_length_nucleotides * 0.25 
            if original_size_bytes == 0 and comp_ratio_denom == 0:
                 compression_ratio = 0.0
            elif comp_ratio_denom == 0:
                compression_ratio = float('inf') if original_size_bytes > 0 else 0.0
            else:
                compression_ratio = original_size_bytes / comp_ratio_denom
            
            bits_per_nt_val = (original_size_bytes * 8) / encoded_dna_length_nucleotides if encoded_dna_length_nucleotides != 0 else 0.0

            encode_orig_size_text.value = f"Original size: {original_size_bytes} bytes"
            encode_dna_len_text.value = f"Encoded DNA length: {encoded_dna_length_nucleotides} nucleotides"
            encode_comp_ratio_text.value = f"Compression ratio: {compression_ratio:.2f}"
            encode_bits_per_nt_text.value = f"Bits per nucleotide: {bits_per_nt_val:.2f} bits/nt"
            
            encode_dna_snippet_text.value = raw_dna_sequence[:200]
            encode_save_button.visible = True
            encode_status_text.value = "Encoding successful! Click 'Save Encoded FASTA...' to save."
            encode_status_text.color = ft.colors.GREEN_700 # Use success color

            analysis_tab_is_enabled = False 
            current_analysis_status_messages = []

            if method == "Huffman":
                if huffman_table_for_header: 
                    try:
                        length_counts = prepare_huffman_codeword_length_data(huffman_table_for_header)
                        if any(length_counts.values()):
                            hist_buf = generate_codeword_length_histogram(length_counts)
                            codeword_hist_image.src_base64 = base64.b64encode(hist_buf.getvalue()).decode('utf-8')
                            hist_buf.close()
                            analysis_tab_is_enabled = True
                        else:
                            current_analysis_status_messages.append("Huffman table empty/no codes; histogram not generated.")
                            codeword_hist_image.src_base64 = None 
                    except Exception as plot_ex:
                        current_analysis_status_messages.append(f"Error generating Huffman histogram: {plot_ex}")
                        codeword_hist_image.src_base64 = None
                else: # Should not happen if method is Huffman and encoding was successful
                    current_analysis_status_messages.append("Huffman table data missing for histogram.")
                    codeword_hist_image.src_base64 = None
            else: 
                current_analysis_status_messages.append("Codeword histogram is only applicable for Huffman encoding.")
                codeword_hist_image.src_base64 = None 

            nucleotide_freq_image.src_base64 = None 
            if raw_dna_sequence: 
                try:
                    nucleotide_counts = prepare_nucleotide_frequency_data(raw_dna_sequence)
                    if any(nucleotide_counts.values()): # Check if there are any counts to plot
                        freq_buf = generate_nucleotide_frequency_plot(nucleotide_counts)
                        nucleotide_freq_image.src_base64 = base64.b64encode(freq_buf.getvalue()).decode('utf-8')
                        freq_buf.close()
                        analysis_tab_is_enabled = True 
                    else:
                        current_analysis_status_messages.append("No valid A/T/C/G nucleotides in sequence for frequency plot.")
                        nucleotide_freq_image.src_base64 = None
                except Exception as plot_ex:
                    current_analysis_status_messages.append(f"Error generating nucleotide frequency plot: {plot_ex}")
                    nucleotide_freq_image.src_base64 = None
            else: 
                 current_analysis_status_messages.append("Encoded DNA sequence is empty; nucleotide plot not generated.")
                 nucleotide_freq_image.src_base64 = None
            
            final_analysis_status = " | ".join(msg for msg in current_analysis_status_messages if msg and msg.strip()).strip()
            if not final_analysis_status and analysis_tab_is_enabled : 
                 analysis_status_text.value = "Analysis plots generated successfully."
                 analysis_status_text.color = ft.colors.GREEN_700
            elif not analysis_tab_is_enabled and not final_analysis_status : 
                 analysis_status_text.value = "No analysis plots applicable or generated for the selected options."
                 analysis_status_text.color = ft.colors.ORANGE_ACCENT_700
            else: # There are some messages, potentially errors or info
                analysis_status_text.value = final_analysis_status
                analysis_status_text.color = ft.colors.ORANGE_ACCENT_700 if "Error" in final_analysis_status else ft.colors.BLUE_GREY_400


            if len(app_tabs.tabs) > 2:
                app_tabs.tabs[2].disabled = not analysis_tab_is_enabled


        except FileNotFoundError:
            encode_status_text.value = f"Error: Input file '{input_path}' not found."
            encode_status_text.color = ft.colors.RED_ACCENT_700
            analysis_status_text.value = "Encoding failed, no analysis available."
            analysis_status_text.color = ft.colors.RED_ACCENT_700
            if len(app_tabs.tabs) > 2: app_tabs.tabs[2].disabled = True
        except Exception as ex:
            encode_status_text.value = f"An error occurred during encoding: {ex}"
            encode_status_text.color = ft.colors.RED_ACCENT_700
            analysis_status_text.value = f"Encoding error, no analysis available: {ex}"
            analysis_status_text.color = ft.colors.RED_ACCENT_700
            if len(app_tabs.tabs) > 2: app_tabs.tabs[2].disabled = True
        
        page.update()

    encode_button.on_click = encode_data

    def on_encode_save_file_result(e: ft.FilePickerResultEvent):
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
        controls=encode_tab_content_controls,
        spacing=15,
        scroll=ft.ScrollMode.AUTO,
    )

    # --- Decode Tab UI Controls & Logic ---
    decode_selected_input_file_text = ft.Text("No FASTA file selected.", italic=True)
    decode_status_text = ft.Text("", selectable=True)
    decode_save_button = ft.ElevatedButton(
        "Save Decoded File...", 
        icon=ft.icons.SAVE, 
        visible=False
    )

    def on_decode_file_picker_result(e: ft.FilePickerResultEvent):
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

    def decode_file_data(e):
        nonlocal decoded_bytes_to_save 
        
        decode_status_text.value = "Processing..."
        decode_save_button.visible = False
        decoded_bytes_to_save = b"" 
        page.update()

        input_path = selected_decode_input_file_path.current
        if not input_path:
            decode_status_text.value = "Error: Please select an input FASTA file first."
            decode_status_text.color = ft.colors.RED_ACCENT_700
            page.update()
            return

        try:
            with open(input_path, 'r', encoding='utf-8') as f_in:
                file_content_str = f_in.read()

            parsed_records = from_fasta(file_content_str)
            if not parsed_records:
                decode_status_text.value = f"Error: No valid FASTA records found in '{os.path.basename(input_path)}'."
                decode_status_text.color = ft.colors.RED_ACCENT_700
                page.update()
                return
            
            current_decode_status_messages = [] # For accumulating messages
            if len(parsed_records) > 1:
                current_decode_status_messages.append("Warning: Multiple FASTA records found; processing the first one.")

            header, dna_sequence = parsed_records[0]

            detected_method_str = None
            huffman_table = None
            num_padding_bits = 0
            check_parity = False
            k_val_decode = 7 
            parity_rule_decode = PARITY_RULE_GC_EVEN_A_ODD_T 

            if "method=huffman" in header and "huffman_params={" in header:
                detected_method_str = "huffman"
                try:
                    json_param_field_start = header.find("huffman_params=")
                    json_part_with_key = header[json_param_field_start + len("huffman_params="):]
                    first_bracket_index = json_part_with_key.find('{')
                    if first_bracket_index == -1: raise ValueError("JSON object for huffman_params not found or malformed.")
                    
                    open_brackets = 0
                    json_end_index = -1
                    for i, char_h in enumerate(json_part_with_key[first_bracket_index:]):
                        if char_h == '{': open_brackets += 1
                        elif char_h == '}': open_brackets -= 1
                        if open_brackets == 0:
                            json_end_index = first_bracket_index + i + 1
                            break
                    if json_end_index == -1: raise ValueError("JSON object for huffman_params not properly closed.")
                    
                    params_json_str = json_part_with_key[first_bracket_index:json_end_index]
                    huffman_params = json.loads(params_json_str)
                    huffman_table_str_keys = huffman_params.get('table')
                    num_padding_bits = huffman_params.get('padding')
                    if huffman_table_str_keys is None or num_padding_bits is None: # Check for None explicitly
                        raise ValueError("Essential 'table' or 'padding' missing in huffman_params.")
                    huffman_table = {int(k): v for k, v in huffman_table_str_keys.items()}
                except Exception as json_ex: # Catch more specific JSON errors if possible
                    decode_status_text.value = f"Error: Invalid or corrupt Huffman parameters in header: {json_ex}"
                    decode_status_text.color = ft.colors.RED_ACCENT_700
                    page.update()
                    return
            elif "method=base4_direct" in header:
                detected_method_str = "base4_direct"
            else:
                decode_status_text.value = "Error: Could not reliably determine decoding method from FASTA header."
                decode_status_text.color = ft.colors.RED_ACCENT_700
                page.update()
                return

            if "parity_k=" in header and "parity_rule=" in header: # Parity info expected if added
                check_parity = True
                try:
                    # More robust parsing for parity_k
                    parity_k_str = header.split("parity_k=")[1].split()[0]
                    k_val_decode = int(parity_k_str)
                    
                    parity_rule_str = header.split("parity_rule=")[1].split()[0]
                    if parity_rule_str != PARITY_RULE_GC_EVEN_A_ODD_T: # Check against known rules
                        raise ValueError(f"Unsupported parity rule '{parity_rule_str}' in header.")
                    parity_rule_decode = parity_rule_str
                    
                    if k_val_decode <=0: raise ValueError("Parity k-value from header must be positive.")

                except (IndexError, ValueError) as parity_ex: # Catch parsing or int conversion errors
                    decode_status_text.value = f"Error: Invalid or corrupt parity parameters in header: {parity_ex}"
                    decode_status_text.color = ft.colors.RED_ACCENT_700
                    page.update()
                    return
            
            decoded_bytes_result: bytes
            parity_errors: list[int] = []

            if detected_method_str == "base4_direct":
                decoded_bytes_result, parity_errors = decode_base4_direct(
                    dna_sequence, check_parity=check_parity, k_value=k_val_decode, parity_rule=parity_rule_decode
                )
            elif detected_method_str == "huffman": # Should have huffman_table and num_padding_bits
                 if huffman_table is None or num_padding_bits is None: # Should be caught by earlier checks
                    decode_status_text.value = "Error: Huffman parameters missing for decoding."
                    decode_status_text.color = ft.colors.RED_ACCENT_700
                    page.update()
                    return
                 decoded_bytes_result, parity_errors = decode_huffman(
                    dna_sequence, huffman_table, num_padding_bits, 
                    check_parity=check_parity, k_value=k_val_decode, parity_rule=parity_rule_decode
                )
            else: # Should be caught by earlier check
                decode_status_text.value = "Error: Internal - decoding method not resolved."
                decode_status_text.color = ft.colors.RED_ACCENT_700
                page.update()
                return
            
            decoded_bytes_to_save = decoded_bytes_result 
            
            # Join any accumulated messages with the main status
            final_status_message = " ".join(current_decode_status_messages)
            if final_status_message: final_status_message += " "
            final_status_message += "Decoding successful."
            
            if check_parity and parity_errors:
                final_status_message += f" Parity error(s) detected at 0-based data block(s): {parity_errors}."
                decode_status_text.color = ft.colors.AMBER_ACCENT_700 # Warning color
            else:
                decode_status_text.color = ft.colors.GREEN_700 # Success color

            decode_status_text.value = final_status_message
            decode_save_button.visible = True

        except FileNotFoundError:
            decode_status_text.value = f"Error: Input file '{input_path}' not found."
            decode_status_text.color = ft.colors.RED_ACCENT_700
        except Exception as ex:
            decode_status_text.value = f"An critical error occurred during decoding: {ex}"
            decode_status_text.color = ft.colors.RED_ACCENT_700
        page.update()

    decode_button = ft.ElevatedButton("Decode", on_click=decode_file_data)

    def on_save_decoded_file_result(e: ft.FilePickerResultEvent):
        nonlocal decoded_bytes_to_save
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
            decode_button,
            ft.Divider(),
            ft.Text("Status:", weight=ft.FontWeight.BOLD),
            decode_status_text,
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
                content=ft.Container(encode_tab_content_column, padding=10, alignment=ft.alignment.top_left)
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
