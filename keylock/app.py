import gradio as gr
import os
import tempfile
from PIL import Image, ImageFont # For font checking and mock image generation

# --- Mockups for running standalone if needed ---
class MockCore:
    MAX_KEYS_TO_DISPLAY_OVERLAY = 5
core = MockCore()
__version__ = "1.2.1" # Example version
ICON_EMBED = "📥"
ICON_EXTRACT = "📤"
# --- End Mockups ---

# --- Define a Professional Theme ---
professional_theme = gr.themes.Base(
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
    primary_hue=gr.themes.colors.blue,
    secondary_hue=gr.themes.colors.sky,
    neutral_hue=gr.themes.colors.slate,
    radius_size=gr.themes.sizes.radius_md,
    spacing_size=gr.themes.sizes.spacing_lg,
    
).set(
    # == Main Page & Default Text ==
    body_background_fill="#EDF2F7",        # Overall page background
    body_text_color="#2D3748",             # Default text color for the body

    # == Blocks / Containers (Tabs, Accordions, Cards, Groups) ==
    block_background_fill="white",          # Background of content blocks
    block_border_width="1px",
    block_border_color="#E2E8F0",           # Border color for blocks
    block_label_background_fill="*primary_500", # Background for labels of blocks (e.g., gr.Group)
    block_label_text_color="white",        # Text color for block labels
    block_title_text_color="*neutral_700", # Color for titles within blocks if applicable

    # == Buttons ==
    button_primary_background_fill="*primary_600",
    button_primary_background_fill_hover="*primary_700",
    button_primary_text_color="white",

    button_secondary_background_fill="*neutral_200",
    button_secondary_background_fill_hover="*neutral_300",
    button_secondary_text_color="*neutral_700",

    # == Input Fields (Textbox, Dropdown, etc.) ==
    input_background_fill="white",
    input_border_color="#CBD5E0",
    input_placeholder_color="#A0AEC0",      # Color of placeholder text
    input_text_color="#2D3748",             # Color of text typed into inputs

    # == Checkboxes (Selected State) ==
    # These apply to the checkbox label and the box itself when selected
    checkbox_label_background_fill_selected="*primary_600",
    checkbox_label_text_color_selected="white",
    checkbox_border_color_selected="*primary_600",

    # Note: Sliders will generally pick up the primary_hue.
    # More specific slider properties are less common in .set() and can be complex.
)

def gradio_embed_data(*args): # Mock function
    kv_input, password_embed, _, _, _, output_fname_base = args
    print(f"Mock: Embedding data. KV: '{kv_input[:20]}...', Pass: {'******' if password_embed else 'None'}, OutputBase: {output_fname_base}")
    
    dummy_html_preview = f"<div style='padding:20px; border:2px solid #2B6CB0; background:#EFF6FF; text-align:center; color: #1E40AF; border-radius: 8px;'>Embedded Image Preview for: <strong>{output_fname_base}.png</strong></div>"
    dummy_status = "Mock: Data embedded successfully. Visual markings applied (simulated)."
    
    # Create a dummy PNG file for download testing
    temp_dir = tempfile.gettempdir()
    # Ensure filename ends with .png, even if user includes it
    if output_fname_base.lower().endswith(".png"):
        filename = output_fname_base
    else:
        filename = f"{output_fname_base}.png"
    dummy_file_path = os.path.join(temp_dir, filename)

    try:
        img = Image.new('RGB', (200, 150), color = (70, 130, 180)) # Steel Blue
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 15)
        except IOError:
            font = ImageFont.load_default()
        d.text((10,10), f"KeyLock: {filename}", fill=(255,255,255), font=font)
        img.save(dummy_file_path)
        print(f"Mock: Saved dummy image to {dummy_file_path}")
    except Exception as e: # Fallback if PIL fails or not fully available
        with open(dummy_file_path, "w") as f:
            f.write("This is a mock PNG file (PIL failed).")
        print(f"Mock: Saved basic dummy file to {dummy_file_path} (PIL error: {e})")
    
    return dummy_html_preview, dummy_status, gr.File(value=dummy_file_path, label=f"Download: {filename}")

def gradio_extract_data(*args): # Mock function
    input_stego_extract, password_extract = args
    print(f"Mock: Extracting data. Image: {'Uploaded' if input_stego_extract else 'None'}, Pass: {'******' if password_extract else 'None'}")
    if not input_stego_extract:
        return "Error: No image uploaded for extraction.", "Please upload an image."
    if not password_extract:
        return "Error: No password provided for decryption.", "Please enter the decryption password."
        
    dummy_extracted_data = '{\n  "API_KEY": "mock_value_from_image",\n  "DB_PASS": "mock_secret_decrypted"\n}'
    dummy_status = "Mock: Data extracted successfully from uploaded image."
    return dummy_extracted_data, dummy_status


def build_interface():
    with gr.Blocks(theme=professional_theme, title="KeyLock Secure Steganography") as keylock_app_interface:
        # --- Header Section ---
        gr.Markdown(f"""
        <div align='center' style='margin-bottom:20px; padding-top: 25px;'>
            <span style='font-size:3em; font-weight:bold; color:#2B6CB0;'>🔑 KeyLock</span>
            <h2 style='font-size:1.4em; color:#4A5568; margin-top:8px; font-weight:500;'>Portable API Key Wallet in a PNG Image</h2>
            <p style='font-size:1.05em; color:#718096; margin-top:10px;'>Securely Embed & Extract API [KEY : Value] pairs in PNG Images</p>
        </div>
        <p style='text-align:center; max-width:750px; margin:0 auto 25px auto; font-size:1em; color:#4A5568; line-height:1.6;'>
            KeyLock encrypts your sensitive data using AES-256-GCM and discreetly hides it within PNG images
            via Least Significant Bit (LSB) steganography. Utilize the extracted variables to seamlessly update
            system environment variables or integrate them directly into your applications.
        </p>
        """)

        # --- GitHub Links ---
        gr.HTML("""
        <div align='center' style='margin-bottom:20px; font-size:1em; display: flex; justify-content: center; gap: 20px;'>
            <span style='font-weight:600; color:#4A5568;'>GitHub: <a href='https://github.com/broadfield-dev/KeyLock-API-Wallet' target='_blank' style='color:#2B6CB0; text-decoration:none;'>KeyLock-API-Wallet</a></span>
            <span style='font-weight:600; color:#4A5568;'>Decoder Module: <a href='https://github.com/broadfield-dev/keylock-decode' target='_blank' style='color:#2B6CB0; text-decoration:none;'>keylock-decode</a></span>
        </div>
        """)
        gr.Markdown("<hr style='border: none; border-top: 1px solid #CBD5E0; margin: 25px auto; max-width: 80%;'>")


        with gr.Tabs() as tabs:
            with gr.TabItem(f"{ICON_EMBED} Embed Data"):
                with gr.Row(equal_height=False, variant='compact'):
                    with gr.Column(scale=2, min_width=380):
                        kv_input = gr.Textbox(
                            label="Secret Data (Key:Value Pairs)",
                            placeholder="API_KEY:value\nDB_PASS=secret",
                            info="One per line. Separators: ':' or '='.",
                            lines=8
                        )
                        password_embed = gr.Textbox(
                            label="Encryption Password",
                            type="password",
                            placeholder="Strong, unique password",
                            info="Crucial for securing/retrieving data."
                        )
                        gr.Markdown("<h3 style='font-size:1.1em; color:#2D3748; margin-bottom:8px; margin-top:20px;'>Carrier Image</h3>")
                        generate_carrier_cb = gr.Checkbox(label="Generate new KeyLock Wallet image", value=True)
                        input_carrier_img = gr.Image(
                            label="Or Upload Your Own (PNG recommended)",
                            type="pil",
                            sources=["upload", "clipboard"],
                            visible=False,
                        )
                        gr.Markdown("<h3 style='font-size:1.1em; color:#2D3748; margin-bottom:8px; margin-top:20px;'>Visual Markings (Top-Right)</h3>")
                        show_keys_cb = gr.Checkbox(
                            label=f"Show list of key names (up to {core.MAX_KEYS_TO_DISPLAY_OVERLAY})",
                            value=True,
                            info="If shown, appears below the 'Data Embedded' title. Max width ~30% of image."
                        )
                        gr.Markdown("<p style='font-size:0.9em; color:#718096; margin-bottom:5px;'>A 'KeyLock: Data Embedded' title bar will always be present above the optional key list.</p>")

                        gr.Markdown("<h3 style='font-size:1.1em; color:#2D3748; margin-bottom:8px; margin-top:20px;'>Output</h3>")
                        output_fname_base = gr.Textbox(
                            label="Base Name for Downloaded Stego Image",
                            value="keylock_secure_image",
                            info="E.g., my_secrets. '.png' will be added if not present."
                        )
                        embed_btn = gr.Button(f"Embed Secrets {ICON_EMBED}", variant="primary", elem_id="embed_button")

                    with gr.Column(scale=3, min_width=480):
                        output_stego_html = gr.HTML(label="Final Stego Image Preview")
                        download_stego_file = gr.File(label="Download Your KeyLock Image (PNG)", interactive=False)
                        status_embed = gr.Textbox(
                            label="Embedding Process Status",
                            interactive=False,
                            lines=7,
                            show_copy_button=True
                        )
                generate_carrier_cb.change(fn=lambda gen: gr.update(visible=not gen), inputs=generate_carrier_cb, outputs=input_carrier_img)

            with gr.TabItem(f"{ICON_EXTRACT} Extract Data"):
                with gr.Row(equal_height=False, variant='compact'):
                    with gr.Column(scale=2, min_width=380):
                        input_stego_extract = gr.Image(
                            label="Upload KeyLock Stego Image (Unmodified PNG)",
                            type="pil",
                            sources=["upload", "clipboard"],
                        )
                        password_extract = gr.Textbox(
                            label="Decryption Password",
                            type="password",
                            placeholder="Password used during embedding",
                            info="Must match exactly."
                        )
                        extract_btn = gr.Button(f"Extract Secrets {ICON_EXTRACT}", variant="primary", elem_id="extract_button")

                    with gr.Column(scale=3, min_width=480):
                        extracted_data_disp = gr.Textbox(
                            label="Extracted Secret Data (JSON or Raw)",
                            lines=10,
                            interactive=False,
                            show_copy_button=True
                        )
                        status_extract = gr.Textbox(
                            label="Extraction Process Status",
                            interactive=False,
                            lines=4,
                            show_copy_button=True
                        )

        embed_btn.click(gradio_embed_data,
            inputs=[kv_input, password_embed, input_carrier_img, generate_carrier_cb, show_keys_cb, output_fname_base],
            outputs=[output_stego_html, status_embed, download_stego_file]
        )
        extract_btn.click(gradio_extract_data,
            inputs=[input_stego_extract, password_extract],
            outputs=[extracted_data_disp, status_extract]
        )

        gr.Markdown("""
        <div style="max-width:800px; margin:30px auto 15px auto; padding:20px; background-color: #FFFFFF; border-radius:8px; border: 1px solid #E2E8F0; box-shadow: rgba(0,0,0,0.05) 0px 1px 2px 0px;">
            <h3 style='font-size:1.2em; color:#2D3748; margin-bottom:15px; text-align:left;'>Important Notes:</h3>
            <ul style="padding-left:25px; text-align:left; line-height:1.7; color:#4A5568; font-size:0.95em;">
                <li><strong>Use Downloaded PNG for Extraction:</strong> Copy-pasting images directly from a web browser can alter pixel data, potentially corrupting the embedded LSB information. Always use the originally downloaded file for reliable extraction.</li>
                <li><strong>PNG Format is Crucial:</strong> KeyLock relies on the lossless nature of PNGs. Uploading non-PNG carriers will trigger an automatic conversion to PNG. Re-compressing or converting the stego-image to other formats (like JPEG) will likely result in data loss.</li>
                <li><strong>Password Security:</strong> Employ strong, unique passwords for encryption. There is no password recovery mechanism; if a password is lost, the data embedded with it cannot be retrieved.</li>
                <li><strong>Data Capacity:</strong> The maximum amount of data that can be embedded depends on the dimensions (width x height) of the carrier image. Enabling visual markings (title bar, key list) slightly reduces this capacity as some pixels are used for the overlay before LSB encoding.</li>
            </ul>
        </div>
        """)
        gr.HTML(f"<div style='text-align:center; margin-top:30px; margin-bottom:20px; font-size:0.9em; color:#A0AEC0;'>KeyLock API Key Wallet | v{__version__}</div>")
    return keylock_app_interface

def main():
    print("Starting KeyLock Gradio Application...")
    # Ensure Pillow's ImageDraw is available for mock image generation if needed.
    global ImageDraw
    from PIL import ImageDraw

    try:
        ImageFont.truetype("arial.ttf" if os.name == 'nt' else "DejaVuSans.ttf", 10)
        print("System font (Arial/DejaVuSans) likely available for PIL.")
    except IOError:
        print("Common system font (Arial/DejaVuSans) not found. PIL might use basic bitmap font.")

    keylock_app_interface = build_interface()
    keylock_app_interface.launch(allowed_paths=[tempfile.gettempdir()])

if __name__ == "__main__":
    main()
