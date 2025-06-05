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

from . import core # Use relative import for core module
from . import __version__ # Import version for footer

app_logger = logging.getLogger("keylock_app")
if not app_logger.hasHandlers(): # Basic logging setup if not configured elsewhere
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)

# Theming
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
            if hasattr(input_image_pil, 'format') and input_image_pil.format and input_image_pil.format.upper() != 'PNG':
                original_format_note = (
                    f"Input carrier image was format '{input_image_pil.format}'. "
                    f"It will be processed and saved as PNG. "
                )
                app_logger.warning(
                    f"{original_format_note}If original was lossy (e.g., JPEG), quality is preserved from upload; "
                    f"if it had transparency (e.g., GIF), it will be lost during RGB conversion."
                )
        
        carrier_img = carrier_img.convert("RGB") 
        
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
        primary_hue="indigo",
        secondary_hue="cyan",
        neutral_hue="zinc",
        text_size="md",
        spacing_size="md",
        radius_size="sm",
        font=["System UI", "sans-serif"]
    )
    custom_css = """
    body {
      background: linear-gradient(to right bottom, rgb(44, 62, 80), rgb(80 168 255)); 
      color: #475b60; 
    }
    span {
        color: #fff;
        }
    .gradio-container {
        background: transparent !important;
    }
    .gr-box, .gr-panel, .gr-pill {
        background-color: rgba(44, 62, 80, 0.8) !important; 
        border-color: rgba(189, 195, 199, 0.2) !important; 
    }
    .gr-textbox, .gr-dropdown, .gr-button, .gr-code, .gr-chat-message, .gr-image {
        border-color: rgba(189, 195, 199, 0.3) !important;
        background-color: rgba(52, 73, 94, 0.9) !important; 
        color: #ecf0f1 !important; 
    }
    .gr-button {
        color: #c6c6fc !important;
    .gr-button.gr-button-primary {
        background-color: #1abc9c !important; 
        color: white !important;
        border-color: #16a085 !important;
    }
    .gr-button.gr-button-secondary {
         background-color: #9b59b6 !important; 
         color: white !important;
         border-color: #8e44ad !important;
    }
    .gr-button.gr-button-stop {
        background-color: #e74c3c !important; 
        color: white !important;
        border-color: #c0392b !important;
    }
    .gr-markdown {
        background-color: rgba(44, 62, 80, 0.7) !important; 
        padding: 10px; 
        border-radius: 5px; 
    }
    .gr-markdown h1, .gr-markdown h2, .gr-markdown h3, .gr-markdown h4, .gr-markdown h5, .gr-markdown h6 {
        color: #ecf0f1 !important; 
        border-bottom-color: rgba(189, 195, 199, 0.3) !important; 
    }
    .gr-markdown pre code {
        background-color: rgba(52, 73, 94, 0.95) !important; 
        border-color: rgba(189, 195, 199, 0.3) !important;
    }
    .gr-image div img { /* Style for image preview */
        border: 1px solid #ccc;
        background-color: rgba(52, 73, 94, 0.9) !important;
    }
    .gr-file div button { /* Style for file download button */
        background-color: #1abc9c !important;
        color: white !important;
        border: 1px solid #16a085 !important;
    }
    """
    with gr.Blocks(theme=custom_theme, css=custom_css, title=f"KeyLock Steganography v{__version__}") as keylock_app_interface:
        gr.Markdown(f"<div align='center' style='margin-bottom:15px;'><span style='font-size:2.5em;font-weight:bold;'>🔑 KeyLock v{__version__}</span><h2 style='font-size:1.2em;color:#bdc3c7;margin-top:5px;'>Portable API Key Wallet in a PNG</h2></div>")
        gr.HTML("<div align='center' style='margin-bottom:10px;font-size:0.9em;color:#bdc3c7;'>Securely embed and extract API key-value pairs (or any text) within PNG images using LSB steganography and AES-256-GCM encryption.</div>")
        gr.HTML("<div align='center' style='margin-bottom:15px;font-size:0.9em;'><span style='font-weight:bold;'>GitHub: <a href='https://github.com/broadfield-dev/KeyLock-API-Wallet' target='_blank' style='color:#1abc9c;'>KeyLock-API-Wallet</a> | Decoder Module: <a href='https://github.com/broadfield-dev/keylock-decode' target='_blank' style='color:#1abc9c;'>keylock-decode</a></span></div>")
        gr.HTML("<hr style='border-color: rgba(189, 195, 199, 0.2); margin-bottom:25px;'>")

        with gr.Tabs():
            with gr.TabItem(f"{ICON_EMBED} Embed Data"):
                with gr.Row():
                    with gr.Column(scale=2):
                        embed_kv_input = gr.Textbox(
                            label="Secret Data (Key:Value Pairs, one per line)",
                            placeholder="API_KEY_1: your_secret_value_1\nSERVICE_USER = 'user@example.com'\n# Lines starting with # are ignored",
                            lines=7,
                            info="Enter secrets as Key:Value or Key=Value. Each pair on a new line."
                        )
                        embed_password_input = gr.Textbox(
                            label="Encryption Password",
                            type="password",
                            placeholder="Enter a strong password",
                            info="Required to encrypt data. Keep this safe!"
                        )
                        embed_output_filename_base = gr.Textbox(
                            label="Base Name for Downloaded Stego Image",
                            value="keylock_wallet",
                            info="'.png' will be appended. e.g., 'my_project_secrets'"
                        )
                        with gr.Accordion("Carrier Image Options", open=False):
                            embed_generate_carrier_checkbox = gr.Checkbox(
                                label="Generate new KeyLock Wallet image",
                                value=True,
                                info="Uncheck to upload your own PNG carrier image."
                            )
                            embed_input_image_upload = gr.Image(
                                label="Upload Your Own PNG Carrier (Optional)",
                                type="pil",
                                image_mode="RGB",
                                sources=["upload","clipboard"],
                                visible=False, # Initially hidden
                                show_download_button=False,
                                interactive=True
                            )
                        embed_show_keys_checkbox = gr.Checkbox(
                            label="Show list of key names on image overlay",
                            value=True,
                            info="Displays embedded key names (not values) on the image."
                        )
                        embed_button = gr.Button("Embed Secrets "+ICON_EMBED, variant="primary")

                    with gr.Column(scale=3):
                        gr.Markdown("### Output Image & Status")
                        embed_output_status = gr.Textbox(
                            label="Embedding Status",
                            lines=4,
                            interactive=False,
                            placeholder="Status messages will appear here..."
                        )
                        embed_output_image_html = gr.HTML(
                            label="Preview of Stego Image (Max 480px width)",
                            value="<div style='text-align:center; color:#bdc3c7; padding:20px;'>Image preview will appear here after embedding.</div>"
                        )
                        embed_download_file = gr.File(
                            label="Download Your KeyLock Image (PNG)",
                            interactive=False,
                            file_count="single"
                        )
                
                def toggle_carrier_upload(generate_flag):
                    return gr.update(visible=not generate_flag)

                embed_generate_carrier_checkbox.change(
                    fn=toggle_carrier_upload,
                    inputs=[embed_generate_carrier_checkbox],
                    outputs=[embed_input_image_upload]
                )
                embed_button.click(
                    fn=gradio_embed_data,
                    inputs=[
                        embed_kv_input,
                        embed_password_input,
                        embed_input_image_upload,
                        embed_generate_carrier_checkbox,
                        embed_show_keys_checkbox,
                        embed_output_filename_base
                    ],
                    outputs=[
                        embed_output_image_html,
                        embed_output_status,
                        embed_download_file
                    ]
                )

            with gr.TabItem(f"{ICON_EXTRACT} Extract Data"):
                with gr.Row():
                    with gr.Column(scale=1):
                        extract_stego_image_upload = gr.Image(
                            label="Upload KeyLock PNG Image",
                            type="pil",
                            image_mode="RGB",
                            sources=["upload","clipboard"],
                            show_download_button=False,
                            interactive=True,
                        )
                        extract_password_input = gr.Textbox(
                            label="Decryption Password",
                            type="password",
                            placeholder="Enter the password used during embedding",
                            info="Required to decrypt and extract data."
                        )
                        extract_button = gr.Button("Extract Secrets "+ICON_EXTRACT, variant="primary")
                    
                    with gr.Column(scale=2):
                        gr.Markdown("### Extracted Data & Status")
                        extract_output_status = gr.Textbox(
                            label="Extraction Status",
                            lines=2,
                            interactive=False,
                            placeholder="Status messages will appear here..."
                        )
                        extract_output_data = gr.Textbox(
                            label="Extracted Secret Data",
                            lines=10,
                            interactive=False,
                            placeholder="Extracted data (usually JSON) will appear here...",
                            show_copy_button=True
                        )
                
                extract_button.click(
                    fn=gradio_extract_data,
                    inputs=[
                        extract_stego_image_upload,
                        extract_password_input
                    ],
                    outputs=[
                        extract_output_data,
                        extract_output_status
                    ]
                )
        
        gr.Markdown("<hr style='border-color: rgba(189, 195, 199, 0.1); margin-top: 30px; margin-bottom:10px;'>")
        gr.Markdown(f"<div style='text-align:center; font-size:0.8em; color:#7f8c8d;'>KeyLock-API-Wallet v{__version__}. Use responsibly.</div>")

    return keylock_app_interface

def main():
    app_logger.info(f"Starting KeyLock Gradio Application v{__version__}...")
    try:
        # Attempt to load a common font to check PIL/Pillow font handling
        ImageFont.truetype("DejaVuSans.ttf", 10) # Common on Linux
        app_logger.info("DejaVuSans font found, PIL font rendering should be good.")
    except IOError:
        try:
            ImageFont.truetype("arial.ttf", 10) # Common on Windows
            app_logger.info("Arial font found, PIL font rendering should be good.")
        except IOError:
            app_logger.warning("Common system fonts (DejaVuSans/Arial) not found. PIL might use basic bitmap font if other preferred fonts in core.py are also unavailable. Overlay text quality might be affected.")
    
    keylock_app_interface = build_interface()
    
    # Prepare launch arguments
    launch_args = {"allowed_paths": [tempfile.gettempdir()]}
    
    server_name = os.environ.get('GRADIO_SERVER_NAME')
    server_port = os.environ.get('GRADIO_SERVER_PORT')

    if server_name:
        launch_args["server_name"] = server_name
        app_logger.info(f"Using server_name from environment: {server_name}")
    if server_port:
        try:
            launch_args["server_port"] = int(server_port)
            app_logger.info(f"Using server_port from environment: {server_port}")
        except ValueError:
            app_logger.warning(f"Invalid GRADIO_SERVER_PORT: {server_port}. Using default.")
            

    keylock_app_interface.launch(**launch_args)

if __name__ == "__main__":
    main()
