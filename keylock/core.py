# keylock/core.py
import io
import json
import os
import struct
import logging
import traceback
import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidTag

from PIL import Image, ImageDraw, ImageFont
import numpy as np

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(lineno)d - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

SALT_SIZE = 16; NONCE_SIZE = 12; TAG_SIZE = 16; KEY_SIZE = 32
PBKDF2_ITERATIONS = 390_000; LENGTH_HEADER_SIZE = 4
PREFERRED_FONTS = ["Verdana", "Arial", "DejaVu Sans", "Calibri", "Helvetica", "Roboto-Regular", "sans-serif"]
MAX_KEYS_TO_DISPLAY_OVERLAY = 12

def _get_font(preferred_fonts, base_size):
    fp = None
    for n in preferred_fonts:
        try: ImageFont.truetype(n.lower()+".ttf",10); fp=n.lower()+".ttf"; break
        except IOError:
            try: ImageFont.truetype(n,10); fp=n; break
            except IOError: continue
    if fp:
        try: return ImageFont.truetype(fp, base_size) # base_size assumed to be int
        except IOError: logger.warning(f"Font '{fp}' load failed with size {base_size}. Defaulting.")
    return ImageFont.load_default()

def set_pil_image_format_to_png(image:Image.Image)->Image.Image:
    buf=io.BytesIO(); image.save(buf,format='PNG'); buf.seek(0)
    reloaded=Image.open(buf); reloaded.format="PNG"; return reloaded

def _derive_key(pw:str,salt:bytes)->bytes:
    kdf=PBKDF2HMAC(algorithm=hashes.SHA256(),length=KEY_SIZE,salt=salt,iterations=PBKDF2_ITERATIONS)
    return kdf.derive(pw.encode('utf-8'))

def encrypt_data(data:bytes,pw:str)->bytes:
    s=os.urandom(SALT_SIZE);k=_derive_key(pw,s);a=AESGCM(k);n=os.urandom(NONCE_SIZE)
    ct=a.encrypt(n,data,None); return s+n+ct

def decrypt_data(payload:bytes,pw:str)->bytes:
    ml=SALT_SIZE+NONCE_SIZE+TAG_SIZE;
    if len(payload)<ml: raise ValueError("Payload too short.")
    s,n,ct_tag=payload[:SALT_SIZE],payload[SALT_SIZE:SALT_SIZE+NONCE_SIZE],payload[SALT_SIZE+NONCE_SIZE:]
    k=_derive_key(pw,s);a=AESGCM(k)
    try: return a.decrypt(n,ct_tag,None)
    except InvalidTag: raise ValueError("Decryption failed: Invalid password/corrupted data.")
    except Exception as e: logger.error(f"Decrypt error: {e}",exc_info=True); raise

def _d2b(d:bytes)->str: return ''.join(format(b,'08b') for b in d)
def _b2B(b:str)->bytes:
    if len(b)%8!=0: raise ValueError("Bits not multiple of 8.")
    return bytes(int(b[i:i+8],2) for i in range(0,len(b),8))

def embed_data_in_image(img_obj:Image.Image,data:bytes)->Image.Image:
    img=img_obj.convert("RGB");px=np.array(img);fpx=px.ravel()
    lb=struct.pack('>I',len(data));fp=lb+data;db=_d2b(fp);nb=len(db)
    if nb>len(fpx): raise ValueError(f"Data too large: {nb} bits needed, {len(fpx)} available.")
    for i in range(nb): fpx[i]=(fpx[i]&0xFE)|int(db[i])
    spx=fpx.reshape(px.shape); return Image.fromarray(spx.astype(np.uint8),'RGB')

def extract_data_from_image(img_obj:Image.Image)->bytes:
    img=img_obj.convert("RGB");px=np.array(img);fpx=px.ravel()
    hbc=LENGTH_HEADER_SIZE*8
    if len(fpx)<hbc: raise ValueError("Image too small for header.")
    lb="".join(str(fpx[i]&1) for i in range(hbc))
    try: pl=struct.unpack('>I',_b2B(lb))[0]
    except Exception as e: raise ValueError(f"Header decode error: {e}")
    if pl==0: return b""
    if pl>(len(fpx)-hbc)/8: raise ValueError("Header len corrupted or > capacity.")
    tpb=pl*8; so=hbc; eo=so+tpb
    if len(fpx)<eo: raise ValueError("Image truncated or header corrupted.")
    pb="".join(str(fpx[i]&1) for i in range(so,eo)); return _b2B(pb)

def parse_kv_string_to_dict(kv_str:str)->dict:
    if not kv_str or not kv_str.strip(): return {}
    dd={};
    for ln,ol in enumerate(kv_str.splitlines(),1):
        l=ol.strip()
        if not l or l.startswith('#'): continue
        lc=l.split('#',1)[0].strip();
        if not lc: continue
        p=lc.split('=',1) if '=' in lc else lc.split(':',1) if ':' in lc else []
        if len(p)!=2: raise ValueError(f"L{ln}: Invalid format '{ol}'.")
        k,v=p[0].strip(),p[1].strip()
        if not k: raise ValueError(f"L{ln}: Empty key in '{ol}'.")
        if len(v)>=2 and v[0]==v[-1] and v.startswith(("'",'"')): v=v[1:-1]
        dd[k]=v
    return dd

def generate_keylock_carrier_image(w=800,h=600,msg="KeyLock Wallet")->Image.Image:
    cs,ce=(30,40,50),(70,80,90);img=Image.new("RGB",(w,h),cs);draw=ImageDraw.Draw(img)
    for y_ in range(h):
        i=y_/float(h-1) if h>1 else .5;r_,g_,b_=(int(s_*(1-i)+e_*(i)) for s_,e_ in zip(cs,ce))
        draw.line([(0,y_),(w,y_)],fill=(r_,g_,b_))
    ib=min(w,h)//7;icx,icy=w//2,h//3;cr=ib//2;cb=[(icx-cr,icy-cr),(icx+cr,icy+cr)]
    rw,rh=ib//4,ib//2;rty=icy+int(cr*.2);rb=[(icx-rw//2,rty),(icx+rw//2,rty+rh)]
    kc,ko=(190,195,200),(120,125,130);ow=max(1,int(ib/30))
    draw.ellipse(cb,fill=kc,outline=ko,width=ow);draw.rectangle(rb,fill=kc,outline=ko,width=ow)
    fs=max(16,min(int(w/18),h//8));fnt=_get_font(PREFERRED_FONTS,fs)
    tc=(225,230,235);sc=(max(0,s_-20) for s_ in cs);tx,ty=w/2,h*.68;so=max(1,int(fs/25))
    try:draw.text((tx+so,ty+so),msg,font=fnt,fill=tuple(sc),anchor="mm");draw.text((tx,ty),msg,font=fnt,fill=tc,anchor="mm")
    except AttributeError: # Fallback for older Pillow without anchor="mm"
        bbox=draw.textbbox((0,0),msg,font=fnt) if hasattr(draw,'textbbox') else (0,0)+draw.textsize(msg,font=fnt)
        tw,th=bbox[2]-bbox[0],bbox[3]-bbox[1];ax,ay=(w-tw)/2,ty-(th/2)
        # For shadow, using 'so' (shadow offset) for y like x, instead of 'th' (text_height)
        draw.text((ax+so,ay+so),msg,font=fnt,fill=tuple(sc));draw.text((ax,ay),msg,font=fnt,fill=tc)
    return img

def _get_text_width(draw_obj, text_str, font_obj):
    # Helper for text width, preferring modern Pillow methods
    if hasattr(font_obj, 'getlength'): # Pillow 10.0.0+
        return font_obj.getlength(text_str)
    elif hasattr(draw_obj, 'textlength'): # Pillow 9.2.0+
        return draw_obj.textlength(text_str, font=font_obj)
    elif hasattr(draw_obj, 'textbbox'): # Pillow 8.0.0+
        bbox = draw_obj.textbbox((0, 0), text_str, font=font_obj)
        return bbox[2] - bbox[0]
    else:  # Older Pillow
        try:
            width, _ = draw_obj.textsize(text_str, font=font_obj)
            return width
        except AttributeError:
            if hasattr(font_obj, 'getsize'):
                width, _ = font_obj.getsize(text_str)
                return width
            logger.warning("Could not determine text width with available Pillow methods.")
            return len(text_str) * int(font_obj.size * 0.6) if hasattr(font_obj, 'size') else len(text_str) * 8 # Fallback


def draw_key_list_dropdown_overlay(image: Image.Image, keys: list[str] = None, title: str = "Data Embedded") -> Image.Image:
    if not title and (keys is None or not keys):
        return set_pil_image_format_to_png(image.copy())

    img_overlayed = image.copy(); draw = ImageDraw.Draw(img_overlayed)
    margin = 10; padding = {'title_x':10,'title_y':6,'key_x':10,'key_y':5}; line_spacing = 4
    title_bg_color=(60,60,60); title_text_color=(230,230,90)
    key_list_bg_color=(50,50,50); key_text_color=(210,210,210); ellipsis_color=(170,170,170)
    
    # --- Font and Box Size Calculations ---
    box_w_max_target = int(image.width * 0.30) # Max width for overlay box is 30% of image width
    
    # Dynamic font sizing with min/max caps
    title_font_size = max(10, min(int(image.height * 0.028), int(box_w_max_target * 0.12)))
    title_font = _get_font(PREFERRED_FONTS, title_font_size)
    
    key_font_size = max(9, min(int(image.height * 0.025), int(box_w_max_target * 0.10)))
    key_font = _get_font(PREFERRED_FONTS, key_font_size)
    
    # --- Text Dimensions ---
    title_w_actual = _get_text_width(draw, title, title_font)
    # Get title height using textbbox if available, else textsize
    title_bbox_for_h = draw.textbbox((0,0), title, font=title_font) if hasattr(draw,'textbbox') else (0,0,0,0)+draw.textsize(title,font=title_font)
    title_h_actual = title_bbox_for_h[3] - title_bbox_for_h[1] if title_bbox_for_h[3] > title_bbox_for_h[1] else title_font_size # Fallback for height if bbox is weird

    max_content_w = title_w_actual
    disp_keys, actual_key_text_widths, total_keys_render_h, key_line_heights = [],[],0,[]

    if keys:
        # Prepare display keys, truncate if more than MAX_KEYS_TO_DISPLAY_OVERLAY
        temp_disp_keys = keys[:MAX_KEYS_TO_DISPLAY_OVERLAY-1] + [f"... ({len(keys)-(MAX_KEYS_TO_DISPLAY_OVERLAY-1)} more)"] if len(keys) > MAX_KEYS_TO_DISPLAY_OVERLAY else keys
        for kt in temp_disp_keys:
            disp_keys.append(kt)
            kw = _get_text_width(draw, kt, key_font)
            # Get key text height
            k_bbox_for_h = draw.textbbox((0,0), kt, font=key_font) if hasattr(draw,'textbbox') else (0,0,0,0)+draw.textsize(kt,font=key_font)
            kh = k_bbox_for_h[3] - k_bbox_for_h[1] if k_bbox_for_h[3] > k_bbox_for_h[1] else key_font_size
            
            actual_key_text_widths.append(kw); key_line_heights.append(kh)
            max_content_w = max(max_content_w, kw)
            total_keys_render_h += kh
        if len(disp_keys) > 1: total_keys_render_h += line_spacing * (len(disp_keys) - 1)
    
    # Determine the width of the content box based on text, capped by box_w_max_target
    content_box_w = min(box_w_max_target, max_content_w + 2 * max(padding['title_x'], padding['key_x']))
    content_box_w = max(content_box_w, int(image.width * 0.1)) # Ensure a minimum sensible width e.g. 10% of image width
    
    # --- Title Bar Drawing (Top-Right) ---
    title_bar_h = title_h_actual + 2 * padding['title_y']
    title_bar_x1 = image.width - margin  # Right edge
    title_bar_x0 = title_bar_x1 - content_box_w # Left edge
    title_bar_y0 = margin # Top edge
    title_bar_y1 = title_bar_y0 + title_bar_h # Bottom edge

    draw.rectangle([(title_bar_x0, title_bar_y0), (title_bar_x1, title_bar_y1)], fill=title_bg_color)
    # Center title text horizontally in the title bar
    title_text_x = title_bar_x0 + (content_box_w - title_w_actual) / 2
    title_text_y = title_bar_y0 + padding['title_y']
    draw.text((title_text_x, title_text_y), title, font=title_font, fill=title_text_color)

    # --- Key List Drawing ---
    if disp_keys:
        key_list_box_h_ideal = total_keys_render_h + 2 * padding['key_y']
        key_list_x0, key_list_x1 = title_bar_x0, title_bar_x1 # Same width as title bar
        key_list_y0 = title_bar_y1 # Positioned below title bar
        key_list_y1 = key_list_y0 + key_list_box_h_ideal
        
        # Ensure key list box does not exceed image boundaries
        key_list_x1 = min(key_list_x1, image.width - margin) 
        key_list_y1 = min(key_list_y1, image.height - margin)
        
        current_content_box_w = key_list_x1 - key_list_x0
        current_key_list_box_h = key_list_y1 - key_list_y0

        draw.rectangle([(key_list_x0, key_list_y0), (key_list_x1, key_list_y1)], fill=key_list_bg_color)
        
        current_text_y = key_list_y0 + padding['key_y']
        available_text_width_for_keys = current_content_box_w - 2 * padding['key_x']

        for i, key_text_item in enumerate(disp_keys):
            if i >= len(key_line_heights): break # Safety break

            current_key_h = key_line_heights[i]
            # Check if current key item will fit vertically, if not, try to draw ellipsis
            if current_text_y + current_key_h > key_list_y0 + current_key_list_box_h - padding['key_y']:
                ellipsis_bbox = draw.textbbox((0,0),"...",font=key_font) if hasattr(draw,'textbbox') else (0,0,0,0)+draw.textsize("...",font=key_font)
                ellipsis_h = ellipsis_bbox[3] - ellipsis_bbox[1] if ellipsis_bbox[3] > ellipsis_bbox[1] else key_font_size
                if current_text_y + ellipsis_h <= key_list_y0 + current_key_list_box_h - padding['key_y']:
                    ellipsis_w = _get_text_width(draw, "...", key_font)
                    draw.text((key_list_x0 + (current_content_box_w - ellipsis_w) / 2, current_text_y), "...", font=key_font, fill=ellipsis_color)
                break 
            
            original_key_text_w = actual_key_text_widths[i]
            text_to_draw = key_text_item
            
            # Truncate text with "..." if it's wider than available space
            if original_key_text_w > available_text_width_for_keys:
                temp_text = key_text_item
                while _get_text_width(draw, temp_text + "...", key_font) > available_text_width_for_keys and len(temp_text) > 0:
                    temp_text = temp_text[:-1]
                text_to_draw = temp_text + "..." if len(temp_text) < len(key_text_item) else temp_text
            
            final_key_text_w = _get_text_width(draw, text_to_draw, key_font)
            # Center key text horizontally
            key_text_draw_x = key_list_x0 + padding['key_x'] + max(0, (available_text_width_for_keys - final_key_text_w) / 2)
            
            text_color_to_use = ellipsis_color if "..." in text_to_draw or f"... ({len(keys)-(MAX_KEYS_TO_DISPLAY_OVERLAY-1)} more)" == key_text_item else key_text_color
            draw.text((key_text_draw_x, current_text_y), text_to_draw, font=key_font, fill=text_color_to_use)
            current_text_y += current_key_h
            if i < len(disp_keys) - 1: current_text_y += line_spacing
            
    return set_pil_image_format_to_png(img_overlayed)
