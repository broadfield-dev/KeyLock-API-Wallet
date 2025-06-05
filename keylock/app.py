# keylock/app.py
import gradio as gr
from PIL import Image, ImageFont
import tempfile
import os
import json
import logging
import traceback
import base64
import io

from . import core  # Use relative import for core module
from . import __version__ # Import version for footer
# from . import hub_utils # Removed import for hub_utils

app_logger = logging.getLogger("keylock_app")
if not app_logger.hasHandlers(): # Basic logging setup if not configured elsewhere
    handler = logging.StreamHandler()
    formatter = gr.formatters.Json("full") # Using Gradio's formatter as an example, though a standard one is fine
    # Standard formatter if gradio.formatters is not available or preferred
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)

# Theming (remains as per your Gradio 3.x compatible code)
try:
    font_family = [gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"]
except AttributeError:
    app_logger.warning("gr.themes.GoogleFont not found. Using fallback fonts. This might be due to Gradio version.")
    font_family = ["ui-sans-serif", "system-ui", "sans-serif"]

try:
    blue_color = gr.themes.colors.blue
    sky_color = gr.themes.colors.sky
    slate_color = gr.themes.colors.slate
    cyan_color = gr.themes.colors.cyan
    neutral_color = gr.themes.colors.neutral
except AttributeError:
    app_logger.warning("gr.themes.colors not found. Using placeholder colors for themes. This might be due to Gradio version.")
    class FallbackColors: # Basic fallback colors
        blue = "blue"; sky = "skyblue"; slate = "slategray"; cyan = "cyan"; neutral = "gray"
    blue_color = FallbackColors.blue
    sky_color = FallbackColors.sky
    slate_color = FallbackColors.slate
    cyan_color = FallbackColors.cyan
    neutral_color = FallbackColors.neutral

ICON_EMBED = "➕"
ICON_EXTRACT = "➖"

def pil_to_base64_html(pil_image, max_width_px=None):
    buffered = io.BytesIO(); pil_image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    style = f"max-width:{max_width_px}px; height:auto; border:1px solid #ccc; display:block; margin-left:auto; margin-right:auto;" if max_width_px else "border:1px solid #ccc; display:block; margin-left:auto; margin-right:auto;"
    return f"<div style='text-align:center;'><img src='data:image/png;base64,{img_str}' alt='Stego Image' style='{style}'/></div>"

def gradio_embed_data(kv_string: str, password: str,
                      input_image_pil: Image.Image, generate_carrier_flag: bool,
                      show_keys_on_image_flag: bool, output_filename_base: str):
    output_html_img_str, status_msg, dl_file_path = None, "An error occurred.", None
    if not password: return None, "Error: Password cannot be empty.", None
    if not kv_string or not kv_string.strip(): return None, "Error: Key-Value data cannot be empty.", None
    try:
        data_dict = core.parse_kv_string_to_dict(kv_string)
        if not data_dict: return None, "Error: Parsed Key-Value data is empty.", None

        original_format_note = ""
        if generate_carrier_flag or input_image_pil is None:
            carrier_img = core.generate_keylock_carrier_image()
        else:
            carrier_img = input_image_pil.copy()
            # Check format of uploaded image
            if hasattr(input_image_pil, 'format') and input_image_pil.format and input_image_pil.format.upper() != 'PNG':
                original_format_note = (
                    f"Input carrier image was format '{input_image_pil.format}'. "
                    f"It will be processed and saved as PNG. "
                )
                app_logger.warning(
                    f"{original_format_note}If original was lossy (e.g., JPEG), quality is preserved from upload; "
                    f"if it had transparency (e.g., GIF), it will be lost during RGB conversion."
                )

        carrier_img = carrier_img.convert("RGB") # Ensure RGB for LSB and overlay consistency

        keys_for_overlay = list(data_dict.keys()) if show_keys_on_image_flag else None
        overlay_title = "KeyLock: Data Embedded"

        final_carrier_with_overlay = core.draw_key_list_dropdown_overlay(
            carrier_img,
            keys=keys_for_overlay,
            title=overlay_title
        )

        serial_data = json.dumps(data_dict).encode('utf-8')
        encrypted_data = core.encrypt_data(serial_data, password)

        stego_final_img = core.embed_data_in_image(final_carrier_with_overlay, encrypted_data)
        stego_final_img = core.set_pil_image_format_to_png(stego_final_img)

        fname_base = "".join(c if c.isalnum() or c in ('_','-') else '_' for c in output_filename_base.strip()) or "keylock_img"
        temp_fp = None
        with tempfile.NamedTemporaryFile(prefix=fname_base+"_", suffix=".png", delete=False) as tmp:
            stego_final_img.save(tmp, format="PNG")
            temp_fp = tmp.name

        output_html_img_str = pil_to_base64_html(stego_final_img, max_width_px=480)
        status_msg = (f"Data embedded into '{os.path.basename(temp_fp)}'.\n"
                      f"{original_format_note}"
                      f"Image contains visual \"{overlay_title}\" overlay "
                      f"{'(with key list)' if show_keys_on_image_flag and keys_for_overlay else ''} "
                      f"and your LSB-encoded secret data.\n"
                      f"Secrets: {len(serial_data)}B (raw), {len(encrypted_data)}B (encrypted).")
        return output_html_img_str, status_msg, temp_fp
    except ValueError as e: return None, f"Error: {str(e)}", None
    except Exception as e: app_logger.error(f"Embed Error: {e}", exc_info=True); return None, f"Unexpected Error: {str(e)}", None

def gradio_extract_data(stego_image_pil: Image.Image, password: str):
    if stego_image_pil is None: return "Error: No image provided.", "Error: No image."
    if not password: return "Error: Password cannot be empty.", "Error: Password required."
    try:
        stego_image_rgb = stego_image_pil.convert("RGB")
        if hasattr(stego_image_pil, 'format') and stego_image_pil.format and stego_image_pil.format.upper() != "PNG":
            app_logger.warning(f"Uploaded image for extraction is format '{stego_image_pil.format}', not PNG. LSB data may be compromised if not the original KeyLock file.")

        extracted_data = core.extract_data_from_image(stego_image_rgb)
        decrypted_bytes = core.decrypt_data(extracted_data, password)
        try:
            data = json.loads(decrypted_bytes.decode('utf-8'))
            txt, stat = json.dumps(data, indent=2), "Data extracted successfully (JSON)."
        except (json.JSONDecodeError, UnicodeDecodeError):
            try:
                txt = "Decrypted (UTF-8, not JSON):\n"+decrypted_bytes.decode('utf-8')
                stat = "Warning: Decrypted as UTF-8 (not JSON)."
            except UnicodeDecodeError:
                txt = "Decrypted (raw hex, not JSON/UTF-8):\n"+decrypted_bytes.hex()
                stat = "Warning: Decrypted as raw hex."
        return txt, stat
    except ValueError as e: return f"Error: {str(e)}", f"Extraction Failed: {str(e)}"
    except Exception as e: app_logger.error(f"Extract Error: {e}", exc_info=True); return f"Unexpected Error: {str(e)}", f"Error: {str(e)}"


def build_interface():
    custom_theme = gr.themes.Base(
        primary_hue="teal", # Teal for primary actions
        secondary_hue="purple", # Purple for secondary elements
        neutral_hue="zinc", # Zinc for neutral/backgrounds (dark gray)
        text_size="sm", # Smaller text size for a denser, professional look
        spacing_size="md", # Medium spacing
        radius_size="sm", # Small border radius
        font=["System UI", "sans-serif"] # Use system font
    )
    custom_css = """
    body {
      background: linear-gradient(to bottom right, #2c3e50, #34495e); /* Dark blue-gray gradient */
      color: #ecf0f1; /* Light text color for dark background */
    }
    /* Adjust main Gradio container background to be transparent to see body gradient */
    .gradio-container {
        background: transparent !important;
    }
    /* Adjust component backgrounds for contrast against the body gradient */
    .gr-box, .gr-panel, .gr-pill {
        background-color: rgba(44, 62, 80, 0.8) !important; /* Slightly lighter transparent dark blue-gray */
        border-color: rgba(189, 195, 199, 0.2) !important; /* Light border for contrast */
    }
    /* Adjust inputs, dropdowns, buttons etc. for visibility */
    .gr-textbox, .gr-dropdown, .gr-button, .gr-code, .gr-chat-message {
        border-color: rgba(189, 195, 199, 0.3) !important;
        background-color: rgba(52, 73, 94, 0.9) !important; /* Slightly different dark blue-gray */
        color: #ecf0f1 !important; /* Ensure text is light */
    }
    .gr-button.gr-button-primary {
        background-color: #1abc9c !important; /* Teal from primary_hue */
        color: white !important;
        border-color: #16a085 !important;
    }
    .gr-button.gr-button-secondary {
         background-color: #9b59b6 !important; /* Purple from secondary_hue */
         color: white !important;
         border-color: #8e44ad !important;
    }
    .gr-button.gr-button-stop {
        background-color: #e74c3c !important; /* Red for stop/delete */
        color: white !important;
        border-color: #c0392b !important;
    }
    /* Adjust markdown backgrounds */
    .gr-markdown {
        background-color: rgba(44, 62, 80, 0.7) !important; /* Transparent dark background */
        padding: 10px; /* Add some padding */
        border-radius: 5px; /* Rounded corners */
    }
    /* Style markdown headers for better contrast */
    .gr-markdown h1, .gr-markdown h2, .gr-markdown h3, .gr-markdown h4, .gr-markdown h5, .gr-markdown h6 {
        color: #ecf0f1 !important; /* Ensure headers are light */
        border-bottom-color: rgba(189, 195, 199, 0.3) !important; /* Light separator */
    }
    /* Style code blocks within markdown */
    .gr-markdown pre code {
        background-color: rgba(52, 73, 94, 0.95) !important; /* Darker code background */
        border-color: rgba(189, 195, 199, 0.3) !important;
    }
    /* Chatbot specific styling */
    .gr-chatbot {
        background-color: rgba(44, 62, 80, 0.7) !important;
        border-color: rgba(189, 195, 199, 0.2) !important;
    }
    .gr-chatbot .message {
        background-color: rgba(52, 73, 94, 0.9) !important; /* Dark background for messages */
        color: #ecf0f1 !important;
        border-color: rgba(189, 195, 199, 0.3) !important;
    }
    .gr-chatbot .message.user {
        background-color: rgba(46, 204, 113, 0.9) !important; /* Greenish background for user messages */
        color: black !important; /* Dark text for green background */
    }
    """
    with gr.Blocks(css=custom_css, title="KeyLock Secure Steganography") as keylock_app_interface:
        gr.Markdown("<div align='center' style='margin-bottom:15px;'><span style='font-size:2.5em;font-weight:bold;'>🔑 KeyLock</span><h2 style='font-size:1.2em;color:#4A5568;margin-top:5px;'>Portable API key wallet in a PNG image</h2><p>Securely Embed & Extract API [KEY : Value] pairs in PNG Images</p></div><p style='text-align:center;max-width:700px;margin:0 auto 20px auto;font-size:1em;color:#4A5568;'>KeyLock encrypts data (AES-256-GCM), hides it in PNGs (LSB).  Use the decoded variables to update the system variables.</p>")
        gr.HTML("<div align='center' style='margin-bottom:15px;'><span style='font-size:1em;font-weight:bold;'>Github: <a href='https://github.com/broadfield-dev/KeyLock-API-Wallet'>github.com/broadfield-dev/KeyLock-API-Wallet</p>")
        gr.HTML("<div align='center' style='margin-bottom:15px;'><span style='font-size:1em;font-weight:bold;'>Decoder Module Github: <a href='https://github.com/broadfield-dev/keylock-decode'>github.com/broadfield-dev/keylock-decode</p>")
        gr.HTML("<hr style='margin-bottom:25px;'>")

        # Removed Hugging Face API Token Accordion as the related tabs are removed

        # --- Main Application Tabs ---
        with gr.Tabs():
            with gr.TabItem("🔐 Embed Data (Create Image)"):
                with gr.Row():
                    kv_input_embed = gr.Textbox(label="Key: Value Pairs (one per line, # for comments)", lines=10, placeholder="api_key: sk-...\nanother_secret = abc...", interactive=True)
                    password_input_embed = gr.Textbox(label="Encryption Password", type="password", placeholder="Choose a strong password", interactive=True)
                with gr.Row():
                    input_image_upload_embed = gr.Image(label="Optional Carrier Image (.png)", type="pil", tool="editor", height=200, interactive=True)
                    generate_carrier_checkbox = gr.Checkbox(label="Generate New Carrier Image", value=True, info="Ignore uploaded image and generate a new one.")
                with gr.Row():
                    show_keys_on_image_checkbox = gr.Checkbox(label="Show Keys Overlay on Image", value=True, info="Visually list keys on the image (not secret).")
                    output_filename_base_input = gr.Textbox(label="Output Filename Base", placeholder="my_secrets_image", value="keylock_secrets")
                embed_button = gr.Button("Embed Data", variant="primary")
                embed_output_image = gr.HTML(label="Generated Stego Image")
                embed_status_text = gr.Textbox(label="Status", lines=3, interactive=False)
                embed_download_file = gr.File(label="Download Image")

                embed_button.click(
                    fn=gradio_embed_data,
                    inputs=[
                        kv_input_embed, password_input_embed,
                        input_image_upload_embed, generate_carrier_checkbox,
                        show_keys_on_image_checkbox, output_filename_base_input
                    ],
                    outputs=[embed_output_image, embed_status_text, embed_download_file]
                )

            with gr.TabItem("🔓 Extract Data (From Image)"):
                with gr.Row():
                    stego_image_upload_extract = gr.Image(label="Upload Stego Image (.png)", type="pil", tool="editor", height=200, interactive=True)
                    password_input_extract = gr.Textbox(label="Decryption Password", type="password", placeholder="Enter the password used for embedding", interactive=True)
                extract_button = gr.Button("Extract Data", variant="primary")
                extracted_kv_output = gr.Textbox(label="Extracted Data", lines=10, interactive=False, placeholder="Extracted Key: Value pairs will appear here.")
                extract_status_text = gr.Textbox(label="Status", lines=1, interactive=False)

                extract_button.click(
                    fn=gradio_extract_data,
                    inputs=[stego_image_upload_extract, password_input_extract],
                    outputs=[extracted_kv_output, extract_status_text]
                )

            # Removed gr.TabItem("🚀 Create New Space") and its contents
            # Removed gr.TabItem("📂 Browse & Edit Space Files") and its contents
            # Removed inner functions handle_load_space_files_list and handle_file_selected_for_editing


def main():
    app_logger.info("Starting KeyLock Gradio Application...")
    try:
        # Use standard font names that PIL usually finds or falls back gracefully on
        ImageFont.truetype("arial.ttf" if os.name == 'nt' else "DejaVuSans.ttf", 10)
        app_logger.info("System font (Arial/DejaVuSans) likely available for PIL.")
    except IOError:
        app_logger.warning("Common system font (Arial/DejaVuSans) not found. PIL might use basic bitmap font if other preferred fonts in core.py are also unavailable.")

    keylock_app_interface = build_interface()
    # Use a more general allowed_paths or configure tempfile location if needed
    keylock_app_interface.launch(allowed_paths=[tempfile.gettempdir()])

if __name__ == "__main__":
    main()
