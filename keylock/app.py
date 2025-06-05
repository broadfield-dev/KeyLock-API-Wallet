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

def build_interface():
    with gr.Blocks(theme=light_theme, title="KeyLock Secure Steganography") as keylock_app_interface:
        gr.Markdown("<div align='center' style='margin-bottom:15px;'><span style='font-size:2.5em;font-weight:bold;'>🔑 KeyLock</span><h2 style='font-size:1.2em;color:#4A5568;margin-top:5px;'>Portable API key wallet in a PNG image</h2><p>Securely Embed & Extract API [KEY : Value] pairs in PNG Images</p></div><p style='text-align:center;max-width:700px;margin:0 auto 20px auto;font-size:1em;color:#4A5568;'>KeyLock encrypts data (AES-256-GCM), hides it in PNGs (LSB).  Use the decoded variables to update the system variables.</p>")
        gr.HTML("<div align='center' style='margin-bottom:15px;'><span style='font-size:1em;font-weight:bold;'>Github: <a href='https://github.com/broadfield-dev/KeyLock-API-Wallet'>github.com/broadfield-dev/KeyLock-API-Wallet</p>")
        gr.HTML("<div align='center' style='margin-bottom:15px;'><span style='font-size:1em;font-weight:bold;'>Decoder Module Github: <a href='https://github.com/broadfield-dev/keylock-decode'>github.com/broadfield-dev/keylock-decode</p>")
        gr.HTML("<hr style='margin-bottom:25px;'>")

        with gr.Tabs():
            with gr.TabItem(f"{ICON_EMBED} Embed Data"):
                with gr.Row(equal_height=False):
                    with gr.Column(scale=2, min_width=350):
                        kv_input = gr.Textbox(label="Secret Data (Key:Value Pairs)",placeholder="API_KEY:value\nDB_PASS=secret",info="One per line. Separators: ':' or '='.",lines=8)
                        password_embed = gr.Textbox(label="Encryption Password",type="password",placeholder="Strong, unique password",info="Crucial for securing/retrieving data.")
                        gr.Markdown("<h3 style='margin-bottom:8px;margin-top:15px;'>Carrier Image</h3>")
                        generate_carrier_cb = gr.Checkbox(label="Generate new KeyLock Wallet image",value=True)
                        # MODIFIED LABEL HERE:
                        input_carrier_img = gr.Image(label="Or Upload Your Own (PNG recommended, other formats converted)",type="pil",sources=["upload","clipboard"],visible=False)
                        gr.Markdown("<h3 style='margin-bottom:8px;margin-top:15px;'>Visual Markings (Top-Right)</h3>")
                        show_keys_cb = gr.Checkbox(label=f"Show list of key names (up to {core.MAX_KEYS_TO_DISPLAY_OVERLAY})",value=True,info="If shown, appears below the 'Data Embedded' title. Max width ~30% of image.")
                        gr.Markdown("<p style='font-size:0.9em;margin-bottom:5px;'>A 'KeyLock: Data Embedded' title bar will always be present above the optional key list.</p>")
                        gr.Markdown("<h3 style='margin-bottom:8px;margin-top:15px;'>Output</h3>")
                        output_fname_base = gr.Textbox(label="Base Name for Downloaded Stego Image",value="keylock_secure_image",info="E.g., my_secrets.png.")
                        embed_btn = gr.Button(f"Embed Secrets {ICON_EMBED}",variant="primary")
                    with gr.Column(scale=3, min_width=450):
                        output_stego_html = gr.HTML(label="Final Stego Image Preview")
                        download_stego_file = gr.File(label="Download Your KeyLock Image (PNG)",interactive=False) 
                        status_embed = gr.Textbox(label="Embedding Process Status",interactive=False,lines=7,show_copy_button=True)
                generate_carrier_cb.change(lambda gen:gr.update(visible=not gen),generate_carrier_cb,input_carrier_img)
            
            with gr.TabItem(f"{ICON_EXTRACT} Extract Data"):
                with gr.Row(equal_height=False):
                    with gr.Column(scale=2, min_width=350):
                        input_stego_extract = gr.Image(
                            label="Upload KeyLock Stego Image (Unmodified PNG from download)",
                            type="pil",
                            sources=["upload","clipboard"] 
                        )
                        password_extract = gr.Textbox(label="Decryption Password",type="password",placeholder="Password used during embedding",info="Must match exactly.")
                        extract_btn = gr.Button(f"Extract Secrets {ICON_EXTRACT}",variant="primary")
                    with gr.Column(scale=3, min_width=450):
                        extracted_data_disp = gr.Textbox(label="Extracted Secret Data (JSON or Raw)",lines=10,interactive=False,show_copy_button=True)
                        status_extract = gr.Textbox(label="Extraction Process Status",interactive=False,lines=4,show_copy_button=True)

        embed_btn.click(gradio_embed_data,
            [kv_input,password_embed,input_carrier_img,generate_carrier_cb,show_keys_cb,output_fname_base],
            [output_stego_html,status_embed,download_stego_file])
        extract_btn.click(gradio_extract_data,
            [input_stego_extract,password_extract],
            [extracted_data_disp,status_extract])
        
        gr.Markdown("""---<div style="max-width:750px;margin:15px auto;font-size:0.95em;"><h3 style='margin-bottom:10px;text-align:left;'>Important Notes:</h3><ul style="padding-left:20px;text-align:left;line-height:1.6;"><li><strong>Use Downloaded PNG for Extraction:</strong> Copy-pasting images from browser can corrupt LSB data. Always use the downloaded file.</li><li><strong>PNG Format is Crucial:</strong> Non-PNG or re-compressed images will likely lose data. KeyLock will attempt to convert uploaded non-PNG carriers to PNG.</li><li><strong>Password Security:</strong> Use strong, unique passwords. Lost passwords mean lost data.</li><li><strong>Data Capacity:</strong> The amount of data depends on image size. The visual overlay slightly reduces capacity by modifying some pixels before LSB encoding.</li></ul></div>""")
        gr.HTML(f"<div style='text-align:center;margin-top:20px;font-size:0.9em;color:#777;'>KeyLock API Key Wallet | v{__version__}</div>")
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
