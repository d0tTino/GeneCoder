import flet as ft
import os # For path operations like getting filename
import json # For Huffman params in FASTA header

# Project module imports
from genecoder.encoders import encode_base4_direct, decode_base4_direct
from genecoder.huffman_coding import encode_huffman, decode_huffman
from genecoder.formats import to_fasta, from_fasta
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T
# add_parity_to_sequence, strip_and_verify_parity are used by encoders/huffman_coding

# This will store the raw FASTA string for the Encode tab's save operation
# It's a Ref because it's tied to a hidden Text control.
encode_fasta_data_to_save_ref = ft.Ref[str]() 
# This will store raw bytes for the Decode tab's save operation.
# It's a simple variable in the main scope, not a Ref to a control,
# as ft.Text.value (if used for hidden storage) expects a string.
decoded_bytes_to_save: bytes = b"" 


def main(page: ft.Page):
    page.title = "GeneCoder"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    
    # --- State variables (Refs for UI interaction if needed, or simple vars) ---
    selected_encode_input_file_path = ft.Ref[str]() # For Encode tab
    selected_encode_input_file_path.current = "" 

    selected_decode_input_file_path = ft.Ref[str]() # For Decode tab
    selected_decode_input_file_path.current = ""

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

    # Encoding Options (remains the same)
    method_dropdown = ft.Dropdown(
        label="Encoding Method",
        options=[
            ft.dropdown.Option("Base-4 Direct"),
            ft.dropdown.Option("Huffman"),
        ],
        value="Base-4 Direct" # Default value
    )

    k_value_input = ft.TextField(
        label="k-value (for parity)", 
        value="7", 
        width=150, 
        disabled=True, # Initially disabled
        keyboard_type=ft.KeyboardType.NUMBER
    )

    parity_checkbox = ft.Checkbox(
        label="Add Parity", 
        value=False,
        on_change=lambda e: setattr(k_value_input, 'disabled', not e.control.value) or page.update()
    )
    
    # Action Button
    encode_button = ft.ElevatedButton("Encode")

    # Output/Metrics Display
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

    # Save Button
    encode_save_button = ft.ElevatedButton(
        "Save Encoded FASTA...", 
        icon=ft.icons.SAVE,
        visible=False 
    )
    
    # Hidden control to store FASTA data for encoding
    encode_hidden_fasta_content = ft.Text(ref=encode_fasta_data_to_save_ref, visible=False, value="")

    # --- Encode Event Handlers ---
    def encode_data(e):
        nonlocal decoded_bytes_to_save # To ensure we clear it if switching operations
        decoded_bytes_to_save = b"" 
        
        # 1. Clear previous status/metrics
        encode_status_text.value = "Processing..."
        encode_orig_size_text.value = "Original size: - bytes"
        encode_dna_len_text.value = "Encoded DNA length: - nucleotides"
        encode_comp_ratio_text.value = "Compression ratio: -"
        encode_bits_per_nt_text.value = "Bits per nucleotide: - bits/nt"
        encode_dna_snippet_text.value = ""
        encode_save_button.visible = False
        encode_hidden_fasta_content.value = ""
        page.update()

        # 2. Get input file path
        input_path = selected_encode_input_file_path.current
        if not input_path:
            encode_status_text.value = "Error: No input file selected."
            page.update()
            return

        # 3. Get encoding method
        method = method_dropdown.value
        
        # 4. Get parity options
        add_parity_encode = parity_checkbox.value # Renamed to avoid conflict
        k_val_encode = 7 # Default
        if add_parity_encode:
            try:
                k_val_encode = int(k_value_input.value)
                if k_val_encode <= 0:
                    encode_status_text.value = "Error: k-value must be a positive integer."
                    page.update()
                    return
            except ValueError:
                encode_status_text.value = "Error: k-value must be an integer."
                page.update()
                return
        
        try:
            # 5. Read input file content
            with open(input_path, 'rb') as f_in:
                input_data = f_in.read()

            raw_dna_sequence = ""
            huffman_table_for_header = {} # Ensure these are reset or correctly scoped
            num_padding_bits_for_header = 0
            
            # 6. Call Core Logic
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

            # 7. Format to FASTA
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
            encode_hidden_fasta_content.value = final_fasta_str # Store for saving

            # 8. Display Metrics
            original_size_bytes = len(input_data)
            encoded_dna_length_nucleotides = len(raw_dna_sequence) # Length of DNA before FASTA formatting

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
            
            # 9. Display DNA snippet
            encode_dna_snippet_text.value = raw_dna_sequence[:200]

            # 10. Enable/show save_button
            encode_save_button.visible = True
            
            # 11. Update status_text
            encode_status_text.value = "Encoding successful!"

        except FileNotFoundError:
            encode_status_text.value = f"Error: Input file '{input_path}' not found."
        except Exception as ex:
            encode_status_text.value = f"An error occurred: {ex}"
        
        page.update()

    encode_button.on_click = encode_data

    def on_encode_save_file_result(e: ft.FilePickerResultEvent):
        if e.path:
            try:
                with open(e.path, "w", encoding="utf-8") as f_out:
                    f_out.write(encode_hidden_fasta_content.value) # Use value from Ref
                encode_status_text.value = f"File saved successfully to {e.path}"
            except Exception as ex:
                encode_status_text.value = f"Error saving file: {ex}"
        else:
            encode_status_text.value = "Save cancelled."
        page.update()

    encode_save_file_picker = ft.FilePicker(on_result=on_encode_save_file_result)
    page.overlay.append(encode_save_file_picker)

    encode_save_button.on_click = lambda _: encode_save_file_picker.save_file(
        dialog_title="Save Encoded FASTA File",
        file_name="encoded_output.fasta",
        allowed_extensions=["fasta", "fa"]
    )


    # --- Layout for Encode Tab ---
    encode_tab_content_controls = [
        ft.Row([encode_browse_button, encode_selected_input_file_text], alignment=ft.MainAxisAlignment.START),
        ft.Row([
            method_dropdown,
            parity_checkbox,
            k_value_input
        ], alignment=ft.MainAxisAlignment.START),
        encode_button,
        ft.Divider(),
        ft.Text("Results:", weight=ft.FontWeight.BOLD),
        encode_status_text,
        encode_orig_size_text,
        encode_dna_len_text,
        encode_comp_ratio_text,
        encode_bits_per_nt_text,
        encode_dna_snippet_text,
        encode_save_button,
        encode_hidden_fasta_content 
    ]
    
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
        decode_status_text.value = "" # Clear status on new file selection
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
            allowed_extensions=["fasta", "fa", "txt"] # Allow .txt for FASTA
        )
    )

    def decode_file_data(e):
        nonlocal decoded_bytes_to_save # Allow modification of the variable in main scope
        
        decode_status_text.value = "Processing..."
        decode_save_button.visible = False
        decoded_bytes_to_save = b"" # Clear previous decoded data
        page.update()

        input_path = selected_decode_input_file_path.current
        if not input_path:
            decode_status_text.value = "Error: No input FASTA file selected."
            page.update()
            return

        try:
            with open(input_path, 'r', encoding='utf-8') as f_in:
                file_content_str = f_in.read()

            parsed_records = from_fasta(file_content_str)
            if not parsed_records:
                decode_status_text.value = f"Error: No valid FASTA records found in '{input_path}'."
                page.update()
                return
            
            if len(parsed_records) > 1:
                # For GUI, maybe process all or allow selection, but for now, first record
                decode_status_text.value = "Warning: Multiple FASTA records found. Processing the first one."
                # No page.update() here yet, append to status

            header, dna_sequence = parsed_records[0]

            # Auto-detect parameters
            detected_method_str = None
            huffman_table = None
            num_padding_bits = 0
            check_parity = False
            k_val_decode = 7 # Default
            parity_rule_decode = PARITY_RULE_GC_EVEN_A_ODD_T # Default

            if "method=huffman" in header and "huffman_params={" in header:
                detected_method_str = "huffman"
                try:
                    json_param_field_start = header.find("huffman_params=")
                    json_part_with_key = header[json_param_field_start + len("huffman_params="):]
                    first_bracket_index = json_part_with_key.find('{')
                    if first_bracket_index == -1: raise ValueError("JSON start bracket not found.")
                    
                    open_brackets = 0
                    json_end_index = -1
                    for i, char_h in enumerate(json_part_with_key[first_bracket_index:]):
                        if char_h == '{': open_brackets += 1
                        elif char_h == '}': open_brackets -= 1
                        if open_brackets == 0:
                            json_end_index = first_bracket_index + i + 1
                            break
                    if json_end_index == -1: raise ValueError("JSON end bracket not found.")
                    
                    params_json_str = json_part_with_key[first_bracket_index:json_end_index]
                    huffman_params = json.loads(params_json_str)
                    huffman_table_str_keys = huffman_params.get('table')
                    num_padding_bits = huffman_params.get('padding')
                    if huffman_table_str_keys is None or num_padding_bits is None:
                        raise ValueError("'table' or 'padding' missing in huffman_params.")
                    huffman_table = {int(k): v for k, v in huffman_table_str_keys.items()}
                except Exception as json_ex:
                    decode_status_text.value = f"Error parsing Huffman params from header: {json_ex}"
                    page.update()
                    return
            elif "method=base4_direct" in header:
                detected_method_str = "base4_direct"
            else:
                # Try to infer based on content if no method in header? For now, require method.
                decode_status_text.value = "Error: Could not determine decoding method from FASTA header."
                page.update()
                return

            if "parity_k=" in header and "parity_rule=" in header:
                check_parity = True
                try:
                    k_val_decode = int(header.split("parity_k=")[1].split()[0])
                    parity_rule_decode = header.split("parity_rule=")[1].split()[0]
                    if k_val_decode <=0: raise ValueError("k-value must be positive.")
                    if parity_rule_decode != PARITY_RULE_GC_EVEN_A_ODD_T: 
                        raise ValueError(f"Unsupported parity rule: {parity_rule_decode}")
                except Exception as parity_ex:
                    decode_status_text.value = f"Error parsing parity params from header: {parity_ex}"
                    page.update()
                    return
            
            # Call core decoding logic
            decoded_bytes_result: bytes
            parity_errors: list[int] = []

            if detected_method_str == "base4_direct":
                decoded_bytes_result, parity_errors = decode_base4_direct(
                    dna_sequence, check_parity=check_parity, k_value=k_val_decode, parity_rule=parity_rule_decode
                )
            elif detected_method_str == "huffman":
                decoded_bytes_result, parity_errors = decode_huffman(
                    dna_sequence, huffman_table, num_padding_bits, 
                    check_parity=check_parity, k_value=k_val_decode, parity_rule=parity_rule_decode
                )
            
            decoded_bytes_to_save = decoded_bytes_result # Store for saving
            
            current_status = "Decoding successful."
            if check_parity and parity_errors:
                current_status += f" Parity error(s) detected at 0-based data block(s): {parity_errors}."
            decode_status_text.value = current_status
            decode_save_button.visible = True

        except FileNotFoundError:
            decode_status_text.value = f"Error: Input file '{input_path}' not found."
        except Exception as ex:
            decode_status_text.value = f"An error occurred during decoding: {ex}"
        page.update()

    decode_button = ft.ElevatedButton("Decode", on_click=decode_file_data)

    def on_save_decoded_file_result(e: ft.FilePickerResultEvent):
        nonlocal decoded_bytes_to_save
        if e.path:
            try:
                with open(e.path, "wb") as f_out: # Write in binary mode
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
        # Suggest a filename based on original, if possible, or generic.
        # For now, generic.
        file_name="decoded_output.bin" 
    )

    # --- Layout for Decode Tab ---
    decode_tab_content_column = ft.Column(
        controls=[
            ft.Row([decode_browse_button, decode_selected_input_file_text], alignment=ft.MainAxisAlignment.START),
            decode_button,
            ft.Divider(),
            ft.Text("Status:", weight=ft.FontWeight.BOLD),
            decode_status_text,
            decode_save_button,
            # No hidden text for bytes, managed by `decoded_bytes_to_save` variable
        ],
        spacing=15,
        scroll=ft.ScrollMode.AUTO,
    )

    # --- Main App Structure (Tabs) ---
    app_tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(
                text="Encode",
                icon=ft.icons.SEND_AND_ARCHIVE_OUTLINED,
                content=ft.Container(encode_tab_content_column, padding=10) 
            ),
            ft.Tab(
                text="Decode", 
                icon=ft.icons.UNARCHIVE_OUTLINED,
                content=ft.Container(decode_tab_content_column, padding=10)
            ),
            ft.Tab(
                text="Analysis", # Placeholder
                icon=ft.icons.ANALYTICS_OUTLINED,
                content=ft.Text("Analysis tools will be here.", text_align=ft.TextAlign.CENTER)
            )
        ],
        expand=1 # Make Tabs control expand
    )

    page.add(app_tabs)
    page.update()


if __name__ == "__main__":
    ft.app(target=main)
