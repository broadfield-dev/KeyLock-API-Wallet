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

app_logger = logging.getLogger("keylock_app")
if not app_logger.hasHandlers(): # Basic logging setup if not configured elsewhere
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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


try:
    light_theme = gr.themes.Soft(
        primary_hue=blue_color,
        secondary_hue=sky_color,
        neutral_hue=slate_color,
        font=font_family
    ).set(
        block_title_text_weight="600",
        block_label_text_weight="500",
        button_primary_background_fill_hover="#0A58CA",
        button_primary_text_color="white"
    )
except AttributeError:
    app_logger.error("Failed to create gr.themes.Soft. Using default theme.")
    light_theme = None 

try:
    dark_theme = gr.themes.Base( 
        primary_hue=blue_color,
        secondary_hue=cyan_color,
        neutral_hue=neutral_color,
        font=font_family
    ).set(
        body_background_fill="#1E1E1E",
        block_background_fill="#252526",
        block_border_width="1px",
        block_label_background_fill="*neutral_800",
        input_background_fill="#3C3C3C",
        button_primary_background_fill="*primary_600",
        button_primary_background_fill_hover="*primary_500",
        button_primary_text_color="white",
        color_accent_soft="*secondary_800"
    )
except AttributeError:
    app_logger.error("Failed to create gr.themes.Base. Dark theme might not be available or correct.")
    dark_theme = None 


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
    radius_size=gr.themes.sizes.radius_md, # "md" or "lg"
    spacing_size=gr.themes.sizes.spacing_lg, # "md" or "lg" for more breathing room

    # Specific component overrides if needed
    # e.g., tab_background_fill="transparent",
    # tab_text_color_selected="*primary_600",
    # tab_border_color_selected="*primary_600"
    shadow_drop="rgba(0,0,0,0.05) 0px 1px 2px 0px", # Subtle shadow
    shadow_drop_lg="rgba(0,0,0,0.1) 0px 10px 15px -3px, rgba(0,0,0,0.05) 0px 4px 6px -2px" # Softer large shadow
)

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
    app_logger.info("Starting KeyLock Gradio Application...")
    try:
        ImageFont.truetype("arial.ttf" if os.name == 'nt' else "DejaVuSans.ttf", 10)
        app_logger.info("System font (Arial/DejaVuSans) likely available for PIL.")
    except IOError:
        app_logger.warning("Common system font (Arial/DejaVuSans) not found. PIL might use basic bitmap font if other preferred fonts in core.py are also unavailable.")
    
    keylock_app_interface = build_interface()
    keylock_app_interface.launch(allowed_paths=[tempfile.gettempdir()])

if __name__ == "__main__":
    main()
