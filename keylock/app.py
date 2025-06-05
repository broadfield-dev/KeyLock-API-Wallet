import gradio as gr
import os
import tempfile
from PIL import ImageFont # Assuming this is from your original imports for font checking

# --- Mockups for running standalone if needed ---
class MockCore:
    MAX_KEYS_TO_DISPLAY_OVERLAY = 5
core = MockCore()
__version__ = "1.2.0" # Example version
ICON_EMBED = "📥"
ICON_EXTRACT = "📤"
# --- End Mockups ---

# --- Define a Professional Theme ---
# Color Palette:
# Primary Blue: ~#2B6CB0 (Tailwind Blue 700)
# Lighter Blue: ~#4299E1 (Tailwind Blue 500)
# Background Grey: #F7FAFC (Tailwind Gray 50) or #EDF2F7 (Tailwind Gray 100)
# Text Grey (Dark): #2D3748 (Tailwind Gray 800)
# Text Grey (Medium): #4A5568 (Tailwind Gray 700)
# Text Grey (Light): #718096 (Tailwind Gray 600)
# Border Grey: #CBD5E0 (Tailwind Gray 400)

professional_theme = gr.themes.Base(
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
    primary_hue=gr.themes.colors.blue, # Base hue for primary elements
    secondary_hue=gr.themes.colors.sky, # Base hue for secondary (can be adjusted)
    neutral_hue=gr.themes.colors.slate, # Base hue for neutral elements
).set(
    # Body & Background
    body_background_fill="#EDF2F7",        # Very light grey background
    body_text_color="#2D3748",             # Dark slate grey for main text

    # Blocks & Containers (like group, tabs, accordions)
    block_background_fill="white",
    block_border_width="1px",
    block_border_color="#E2E8F0",          # Light grey border (Tailwind Gray 300)
    block_label_background_fill="*primary_500", # Blue for block labels
    block_label_text_color="white",
    block_title_text_color="*neutral_700",

    # Buttons
    button_primary_background_fill="*primary_600", # Main blue (e.g., #2B6CB0)
    button_primary_background_fill_hover="*primary_700",
    button_primary_text_color="white",

    button_secondary_background_fill="*neutral_200", # Lighter grey
    button_secondary_background_fill_hover="*neutral_300",
    button_secondary_text_color="*neutral_700", # Darker grey text for secondary

    # Inputs (Textbox, Dropdown, etc.)
    input_background_fill="white",
    input_border_color="#CBD5E0",          # Medium grey border
    input_placeholder_color="#A0AEC0",      # Lighter grey for placeholder (Tailwind Gray 500)

    # Slider, Checkbox, Radio
    slider_color="*primary_500",
    checkbox_label_background_fill_selected="*primary_600",
    checkbox_label_text_color_selected="white",
    checkbox_border_color_selected="*primary_600",

    # Borders & Dividers
    border_color_accent="*primary_300",
    border_color_primary="#E2E8F0",        # Light grey for general borders

    # Spacing & Radius
    spacing_size=gr.themes.sizes.spacing_lg, # "md" or "lg" for more breathing room

    # Specific component overrides if needed
    # e.g., tab_background_fill="transparent",
    # tab_text_color_selected="*primary_600",
    # tab_border_color_selected="*primary_600"
    shadow_drop="rgba(0,0,0,0.05) 0px 1px 2px 0px", # Subtle shadow
    shadow_drop_lg="rgba(0,0,0,0.1) 0px 10px 15px -3px, rgba(0,0,0,0.05) 0px 4px 6px -2px" # Softer large shadow
)
# --- End Theme Definition ---


def gradio_embed_data(*args): # Mock function
    print("Mock: Embedding data...")
    # Simulate output: HTML for preview, status message, and a dummy file path
    dummy_html_preview = "<div style='padding:20px; border:1px solid #ccc; background:#f9f9f9; text-align:center;'>Embedded Image Preview Would Be Here</div>"
    dummy_status = "Mock: Data embedded successfully. Visual markings applied."
    # Create a dummy file for download testing
    temp_dir = tempfile.gettempdir()
    dummy_file_path = os.path.join(temp_dir, "mock_keylock_image.png")
    with open(dummy_file_path, "w") as f:
        f.write("This is a mock PNG file.")
    return dummy_html_preview, dummy_status, gr.File(value=dummy_file_path, label="Download Your KeyLock Image (PNG)")

def gradio_extract_data(*args): # Mock function
    print("Mock: Extracting data...")
    dummy_extracted_data = '{\n  "API_KEY": "mock_value",\n  "DB_PASS": "mock_secret"\n}'
    dummy_status = "Mock: Data extracted successfully."
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
        # Using Markdown for a themed horizontal rule
        gr.Markdown("<hr style='border: none; border-top: 1px solid #CBD5E0; margin: 25px auto; max-width: 80%;'>")


        with gr.Tabs() as tabs:
            with gr.TabItem(f"{ICON_EMBED} Embed Data"):
                with gr.Row(equal_height=False, variant='compact'): # variant='compact' might reduce some padding
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
                            # height=200, # Optional: constrain height
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
                            info="E.g., my_secrets.png. '.png' will be added."
                        )
                        embed_btn = gr.Button(f"Embed Secrets {ICON_EMBED}", variant="primary", elem_id="embed_button") # Added elem_id for potential CSS

                    with gr.Column(scale=3, min_width=480):
                        output_stego_html = gr.HTML(label="Final Stego Image Preview")
                        download_stego_file = gr.File(label="Download Your KeyLock Image (PNG)", interactive=False)
                        status_embed = gr.Textbox(
                            label="Embedding Process Status",
                            interactive=False,
                            lines=7,
                            show_copy_button=True
                        )

                generate_carrier_cb.change(lambda gen: gr.update(visible=not gen), generate_carrier_cb, input_carrier_img)

            with gr.TabItem(f"{ICON_EXTRACT} Extract Data"):
                with gr.Row(equal_height=False, variant='compact'):
                    with gr.Column(scale=2, min_width=380):
                        input_stego_extract = gr.Image(
                            label="Upload KeyLock Stego Image (Unmodified PNG)",
                            type="pil",
                            sources=["upload", "clipboard"],
                            # height=300 # Optional: constrain height
                        )
                        password_extract = gr.Textbox(
                            label="Decryption Password",
                            type="password",
                            placeholder="Password used during embedding",
                            info="Must match exactly."
                        )
                        extract_btn = gr.Button(f"Extract Secrets {ICON_EXTRACT}", variant="primary", elem_id="extract_button") # Added elem_id

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
            [kv_input, password_embed, input_carrier_img, generate_carrier_cb, show_keys_cb, output_fname_base],
            [output_stego_html, status_embed, download_stego_file]
        )
        extract_btn.click(gradio_extract_data,
            [input_stego_extract, password_extract],
            [extracted_data_disp, status_extract]
        )

        # --- Important Notes Section ---
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

        # --- Footer ---
        gr.HTML(f"<div style='text-align:center; margin-top:30px; margin-bottom:20px; font-size:0.9em; color:#A0AEC0;'>KeyLock API Key Wallet | v{__version__}</div>")

    return keylock_app_interface


def main():
    # app_logger.info("Starting KeyLock Gradio Application...") # Assuming you have app_logger
    print("Starting KeyLock Gradio Application...")
    try:
        # Check for a common system font to give a hint about PIL's capabilities
        ImageFont.truetype("arial.ttf" if os.name == 'nt' else "DejaVuSans.ttf", 10)
        # app_logger.info("System font (Arial/DejaVuSans) likely available for PIL.")
        print("System font (Arial/DejaVuSans) likely available for PIL.")
    except IOError:
        # app_logger.warning("Common system font (Arial/DejaVuSans) not found. PIL might use basic bitmap font if other preferred fonts in core.py are also unavailable.")
        print("Common system font (Arial/DejaVuSans) not found. PIL might use basic bitmap font.")

    keylock_app_interface = build_interface()
    keylock_app_interface.launch(allowed_paths=[tempfile.gettempdir()]) # Add other paths if needed

if __name__ == "__main__":
    main()
