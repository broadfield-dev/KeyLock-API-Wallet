import gradio as gr
import re
import json
import requests
import os
import tempfile

# --- build_logic.py is now a hard requirement ---
from build_logic import (
    create_space as build_logic_create_space,
    _get_api_token as build_logic_get_api_token, # Keep for HF specific ops
    whoami as build_logic_whoami,
    list_space_files_for_browsing,
    get_space_repository_info,
    get_space_file_content,
    update_space_file,
    parse_markdown as build_logic_parse_markdown,
    delete_space_file as build_logic_delete_space_file,
    get_space_runtime_status
)
print("build_logic.py loaded successfully.")
# --- End build_logic import ---

# --- Model Configurations (Imported from models_config.py) ---
from models_config import (
    SUPPORTED_MODELS,
    get_model_config_by_ui_name,
    get_llm_api_key,
    call_llm_api
)
# --- End Model Configurations ---

# Configuration for non-LLM tools (e.g., Web Search)
# These remain separate from the LLM provider configurations.
TOOL_API_KEYS = {
  'HF_SPACES_SEARCH': os.getenv('HF_SPACES_SEARCH_API_KEY', 'YOUR_HF_SPACES_API_KEY') # For Web Search
}
TOOL_API_URLS = {
  'HF_SPACES_SEARCH': os.getenv('HF_SPACES_SEARCH_URL', 'https://broadfield-dev-search-tool.hf.space/scrape') # for Web Search
}


bbb = chr(96) * 3
parsed_code_blocks_state_cache = []
BOT_ROLE_NAME = "assistant" # This is what the AI is instructed to use for ITS role name in responses.
                           # API message roles are handled by models_config.py

DEFAULT_SYSTEM_PROMPT = f"""You are an expert AI programmer. Your role is to generate code and file structures based on user requests, or to modify existing code provided by the user.
When you provide NEW code for a file, or MODIFIED code for an existing file, use the following format exactly:
### File: path/to/filename.ext
(You can add a short, optional, parenthesized description after the filename on the SAME line)
{bbb}language
# Your full code here
{bbb}
If the file is binary, or you cannot show its content, use this format:
### File: path/to/binaryfile.ext
[Binary file - approximate_size bytes]
When you provide a project file structure, use this format:
## File Structure
{bbb}
📁 Root
  📄 file1.py
  📁 subfolder
    📄 file2.js
{bbb}
The role name for your responses in the chat history must be '{BOT_ROLE_NAME}'.
Adhere strictly to these formatting instructions.
If you update a file, provide the FULL file content again under the same filename.
Only the latest version of each file mentioned throughout the chat will be used for the final output.
Filenames in the '### File:' line should be clean paths (e.g., 'src/app.py', 'Dockerfile') and should NOT include Markdown backticks around the filename itself.
If the user provides existing code (e.g., by pasting a Markdown structure), and asks for modifications, ensure your response includes the complete, modified versions of ONLY the files that changed, using the ### File: format. Unchanged files do not need to be repeated by you. The system will merge your changes with the prior state.
If the user asks to delete a file, simply omit it from your next full ### File: list.
If no code is provided, assist the user with their tasks.
"""

# --- Core Utility, Parsing, Export functions (largely unchanged but reviewed) ---
def escape_html_for_markdown(text):
    if not isinstance(text, str): return ""
    return text.replace("&", "&").replace("<", "<").replace(">", ">")

def _infer_lang_from_filename(filename):
    if not filename: return "plaintext"
    if '.' in filename:
        ext = filename.split('.')[-1].lower()
        mapping = {
            'py': 'python', 'js': 'javascript', 'ts': 'typescript', 'jsx': 'javascript', 'tsx': 'typescript',
            'html': 'html', 'htm': 'html', 'css': 'css', 'scss': 'scss', 'sass': 'sass', 'less': 'less',
            'json': 'json', 'xml': 'xml', 'yaml': 'yaml', 'yml': 'yaml', 'toml': 'toml',
            'md': 'markdown', 'rst': 'rst',
            'sh': 'bash', 'bash': 'bash', 'zsh': 'bash', 'bat': 'batch', 'cmd': 'batch', 'ps1': 'powershell',
            'c': 'c', 'h': 'c', 'cpp': 'cpp', 'hpp': 'cpp', 'cs': 'csharp', 'java': 'java',
            'rb': 'ruby', 'php': 'php', 'go': 'go', 'rs': 'rust', 'swift': 'swift', 'kt': 'kotlin', 'kts': 'kotlin',
            'sql': 'sql', 'dockerfile': 'docker', 'tf': 'terraform', 'hcl': 'terraform',
            'txt': 'plaintext', 'log': 'plaintext', 'ini': 'ini', 'conf': 'plaintext', 'cfg': 'plaintext',
            'csv': 'plaintext', 'tsv': 'plaintext', 'err': 'plaintext',
            '.env': 'plaintext', '.gitignore': 'plaintext', '.npmrc': 'plaintext', '.gitattributes': 'plaintext',
            'makefile': 'makefile',
        }
        return mapping.get(ext, "plaintext")
    base_filename = os.path.basename(filename)
    if base_filename == 'Dockerfile': return 'docker'
    if base_filename == 'Makefile': return 'makefile'
    if base_filename.startswith('.'): return 'plaintext'
    return "plaintext"

def _clean_filename(filename_line_content):
    text = filename_line_content.strip()
    text = re.sub(r'[`\*_]+', '', text)
    path_match = re.match(r'^([\w\-\.\s\/\\]+)', text)
    if path_match:
        parts = re.split(r'\s*\(', path_match.group(1).strip(), 1)
        return parts[0].strip() if parts else ""
    backtick_match = re.search(r'`([^`]+)`', text)
    if backtick_match:
        potential_fn = backtick_match.group(1).strip()
        parts = re.split(r'\s*\(|\s{2,}', potential_fn, 1)
        cleaned_fn = parts[0].strip() if parts else ""
        cleaned_fn = cleaned_fn.strip('`\'":;,')
        if cleaned_fn: return cleaned_fn
    parts = re.split(r'\s*\(|\s{2,}', text, 1)
    filename_candidate = parts[0].strip() if parts else text.strip()
    filename_candidate = filename_candidate.strip('`\'":;,')
    return filename_candidate if filename_candidate else text.strip()


def _parse_chat_stream_logic(chat_json_string, existing_files_state=None):
    global parsed_code_blocks_state_cache
    latest_blocks_dict = {}
    if existing_files_state:
        for block in existing_files_state: latest_blocks_dict[block["filename"]] = block.copy()

    results = {"parsed_code_blocks": [], "preview_md": "", "default_selected_filenames": [], "error_message": None}
    try:
        ai_chat_history = json.loads(chat_json_string)
        if not isinstance(ai_chat_history, list): raise ValueError("JSON input must be a list of chat messages.")
    except json.JSONDecodeError as e: results["error_message"] = f"JSON Parsing Error: {e}."; return results
    except ValueError as e: results["error_message"] = str(e); return results

    message_obj = None
    if ai_chat_history and isinstance(ai_chat_history[-1], dict) and ai_chat_history[-1].get("role", "").lower() == BOT_ROLE_NAME:
         message_obj = ai_chat_history[-1]

    if not message_obj:
         results["parsed_code_blocks"] = list(latest_blocks_dict.values())
         results["default_selected_filenames"] = [b["filename"] for b in results["parsed_code_blocks"] if not b.get("is_structure_block")]
         return results

    role, content = message_obj.get("role", "").lower(), message_obj.get("content", "")
    file_pattern = re.compile(r"### File:\s*(?P<filename_line>[^\n]+)\n(?:```(?P<lang>[\w\.\-\+]*)\n(?P<code>[\s\S]*?)\n```|(?P<binary_msg>\[Binary file(?: - [^\]]+)?\]))")
    structure_pattern = re.compile(r"## File Structure\n```(?:(?P<struct_lang>[\w.-]*)\n)?(?P<structure_code>[\s\S]*?)\n```")

    if role == BOT_ROLE_NAME:
        structure_match = structure_pattern.search(content)
        if structure_match:
            latest_blocks_dict["File Structure (original)"] = {"filename": "File Structure (original)", "language": structure_match.group("struct_lang") or "plaintext", "code": structure_match.group("structure_code").strip(), "is_binary": False, "is_structure_block": True}

        current_message_file_blocks = {}
        for match in file_pattern.finditer(content):
            filename = _clean_filename(match.group("filename_line"))
            if not filename: continue
            lang, code_block, binary_msg = match.group("lang"), match.group("code"), match.group("binary_msg")
            item_data = {"filename": filename, "is_binary": False, "is_structure_block": False}
            if code_block is not None:
                item_data["code"], item_data["language"] = code_block.strip(), (lang.strip().lower() if lang else _infer_lang_from_filename(filename))
            elif binary_msg is not None:
                item_data["code"], item_data["language"], item_data["is_binary"] = binary_msg.strip(), "binary", True
            else: continue
            current_message_file_blocks[filename] = item_data
        latest_blocks_dict.update(current_message_file_blocks)

    current_parsed_blocks = list(latest_blocks_dict.values())
    current_parsed_blocks.sort(key=lambda b: (0, b["filename"]) if b.get("is_structure_block") else (1, b["filename"]))
    parsed_code_blocks_state_cache = current_parsed_blocks
    results["parsed_code_blocks"] = current_parsed_blocks
    results["default_selected_filenames"] = [b["filename"] for b in current_parsed_blocks if not b.get("is_structure_block")]
    return results

def _export_selected_logic(selected_filenames, space_line_name_for_md, parsed_blocks_for_export):
    results = {"output_str": "", "error_message": None, "download_filepath": None}
    global parsed_code_blocks_state_cache
    if parsed_blocks_for_export is None:
        parsed_blocks_for_export = parsed_code_blocks_state_cache

    exportable_blocks = [b for b in parsed_blocks_for_export if not b.get("is_structure_block") and not b.get("is_binary") and not (b.get("code", "").startswith("[Error loading content:") or b.get("code", "").startswith("[Binary or Skipped file]"))]
    binary_blocks = [b for b in parsed_blocks_for_export if b.get("is_binary") or b.get("code", "").startswith("[Binary or Skipped file]")]

    if not exportable_blocks and not binary_blocks and not any(b.get("is_structure_block") for b in parsed_blocks_for_export):
        results["output_str"] = f"# Space: {space_line_name_for_md}\n## File Structure\n{bbb}\n📁 Root\n{bbb}\n\n*No files to list in structure or export.*"
        try:
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md", encoding='utf-8') as tmpfile:
                tmpfile.write(results["output_str"]); results["download_filepath"] = tmpfile.name
        except Exception as e: print(f"Error creating temp file for empty export: {e}")
        return results

    output_lines = [f"# Space: {space_line_name_for_md}"]
    structure_block = next((b for b in parsed_blocks_for_export if b.get("is_structure_block")), None)
    if structure_block:
        output_lines.extend(["## File Structure", bbb, structure_block["code"].strip(), bbb, ""])
    else:
        output_lines.extend(["## File Structure", bbb, "📁 Root"])
        filenames_for_structure_list = sorted(list(set(b["filename"] for b in exportable_blocks + binary_blocks)))
        if filenames_for_structure_list:
            for fname in filenames_for_structure_list: output_lines.append(f"  📄 {fname}")
        output_lines.extend([bbb, ""])

    output_lines.append("Below are the contents of all files in the space:\n")
    exported_content = False
    files_to_export_content = []
    if selected_filenames:
        files_to_export_content = [b for b in parsed_blocks_for_export if b["filename"] in selected_filenames and not b.get("is_structure_block")]
    else:
        files_to_export_content = [b for b in parsed_blocks_for_export if not b.get("is_structure_block")]
    files_to_export_content.sort(key=lambda b: (0, b["filename"]) if b.get("is_binary") else (1, b["filename"]))

    for block in files_to_export_content:
        output_lines.append(f"### File: {block['filename']}")
        if block.get('is_binary') or block.get("code", "").startswith("["):
            output_lines.append(block.get('code',''))
        else:
            output_lines.extend([f"{bbb}{block.get('language', 'plaintext') or 'plaintext'}", block.get('code',''), bbb])
        output_lines.append(""); exported_content = True

    if not exported_content and not filenames_for_structure_list: output_lines.append("*No file content selected or available for export.*")
    elif not exported_content and filenames_for_structure_list:  output_lines.append("*Selected files have no content blocks defined by AI, are binary, or encountered loading errors.*")
    final_output_str = "\n".join(output_lines)
    results["output_str"] = final_output_str
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md", encoding='utf-8') as tmpfile:
            tmpfile.write(final_output_str); results["download_filepath"] = tmpfile.name
    except Exception as e: print(f"Error creating temp file: {e}"); results["error_message"] = "Could not prepare file for download."
    return results

# Generic format for internal chat history representation
def _convert_gr_history_to_generic_chat_format(gr_history, current_user_message=None):
    messages = []
    for user_msg, bot_msg in gr_history:
        if user_msg: messages.append({"role": "user", "content": user_msg})
        if bot_msg and isinstance(bot_msg, str): messages.append({"role": "assistant", "content": bot_msg})
    if current_user_message: messages.append({"role": "user", "content": current_user_message})
    return messages


def get_latest_bot_message_as_json(gr_history):
    latest_bot_msg_content = None
    for user_msg, bot_msg in reversed(gr_history):
        if bot_msg and isinstance(bot_msg, str):
            latest_bot_msg_content = bot_msg
            break
    if latest_bot_msg_content is None:
        return json.dumps([])
    return json.dumps([{"role": BOT_ROLE_NAME, "content": latest_bot_msg_content}], indent=2)


def _generate_ui_outputs_from_cache(owner, space_name):
    global parsed_code_blocks_state_cache
    preview_md_val = "*No files in cache to display.*"
    formatted_md_val = f"# Space: {owner}/{space_name}\n## File Structure\n{bbb}\n📁 Root\n{bbb}\n\n*No files in cache.*" if owner or space_name else "*Load or define a Space to see its Markdown structure.*"
    download_file = None

    if parsed_code_blocks_state_cache:
        preview_md_lines = ["## Detected/Updated Files & Content (Latest Versions):"]
        for block in parsed_code_blocks_state_cache:
            preview_md_lines.append(f"\n----\n**File:** `{escape_html_for_markdown(block['filename'])}`")
            if block.get('is_structure_block'): preview_md_lines.append(f" (Original File Structure from AI)\n")
            elif block.get('is_binary'): preview_md_lines.append(f" (Binary File)\n")
            elif block.get('language') and block.get('language') != 'binary': preview_md_lines.append(f" (Language: `{block['language']}`)\n")
            else: preview_md_lines.append("\n")
            content = block.get('code', '')
            if block.get('is_binary') or content.startswith("[") :
                 preview_md_lines.append(f"\n`{escape_html_for_markdown(content)}`\n")
            elif block.get('is_structure_block'):
                 preview_md_lines.append(f"\n{bbb}{block.get('language', 'plaintext') or 'plaintext'}\n{content}\n{bbb}\n")
            else:
                 preview_md_lines.append(f"\n{bbb}{block.get('language', 'plaintext') or 'plaintext'}\n{content}\n{bbb}\n")
        preview_md_val = "\n".join(preview_md_lines)
        space_line_name = f"{owner}/{space_name}" if owner and space_name else (owner or space_name or "your-space")
        export_result = _export_selected_logic(None, space_line_name, parsed_code_blocks_state_cache)
        formatted_md_val = export_result["output_str"]
        download_file = export_result["download_filepath"]
    return formatted_md_val, preview_md_val, gr.update(value=download_file, interactive=download_file is not None)

# Renamed from handle_groq_chat_submit
def handle_llm_chat_submit(user_message, chat_history, llm_api_key_ui_input,
                           llm_model_ui_select, system_prompt_ui_input,
                           hf_owner_name, hf_repo_name, _current_formatted_markdown):
    global parsed_code_blocks_state_cache
    _chat_msg_in, _chat_hist, _status = "", list(chat_history), "Initializing..."
    _detected_files_update, _formatted_output_update, _download_btn_update = gr.update(), gr.update(), gr.update(interactive=False, value=None)

    if user_message and _current_formatted_markdown:
        try:
            parsed_from_md = build_logic_parse_markdown(_current_formatted_markdown)
            structure_block = next((b for b in parsed_code_blocks_state_cache if b.get("is_structure_block")), None)
            parsed_code_blocks_state_cache = []
            if structure_block:
                parsed_code_blocks_state_cache.append(structure_block)
            for f_info in parsed_from_md.get("files", []):
                 if f_info.get("path") and f_info.get("path") != "File Structure (original)":
                      is_binary_repr = isinstance(f_info.get("content"), str) and (f_info["content"].startswith("[Binary file") or f_info["content"].startswith("[Error loading content:") or f_info["content"].startswith("[Binary or Skipped file]"))
                      parsed_code_blocks_state_cache.append({
                           "filename": f_info["path"], "code": f_info.get("content", ""),
                           "language": "binary" if is_binary_repr else _infer_lang_from_filename(f_info["path"]),
                           "is_binary": is_binary_repr, "is_structure_block": False
                      })
            parsed_code_blocks_state_cache.sort(key=lambda b: (0, b["filename"]) if b.get("is_structure_block") else (1, b["filename"]))
        except Exception as e:
            print(f"Error parsing formatted markdown before chat submit: {e}")

    if not user_message.strip():
        _status = "Cannot send an empty message."
        yield (user_message, _chat_hist, _status, _detected_files_update, _formatted_output_update, _download_btn_update); return

    _chat_hist.append((user_message, None)); _status = "Sending to AI..."
    yield (_chat_msg_in, _chat_hist, _status, _detected_files_update, _formatted_output_update, _download_btn_update)

    selected_model_config = get_model_config_by_ui_name(llm_model_ui_select)
    if not selected_model_config:
        _chat_hist[-1] = (user_message, f"Error: Model '{llm_model_ui_select}' not configured."); _status = "Model configuration error."
        yield (_chat_msg_in, _chat_hist, _status, _detected_files_update, _formatted_output_update, _download_btn_update); return

    api_key, key_err = get_llm_api_key(selected_model_config, llm_api_key_ui_input)
    if key_err:
        _chat_hist[-1] = (user_message, f"API Key Error: {key_err}"); _status = "API Key missing or error."
        yield (_chat_msg_in, _chat_hist, _status, _detected_files_update, _formatted_output_update, _download_btn_update); return

    current_sys_prompt = system_prompt_ui_input.strip() or DEFAULT_SYSTEM_PROMPT
    current_files_context = ""
    if parsed_code_blocks_state_cache:
        current_files_context = "\n\n## Current Files in Space\n"
        for block in parsed_code_blocks_state_cache:
            if block.get("is_structure_block"):
                 current_files_context += f"### File: {block['filename']}\n{bbb}\n{block['code']}\n{bbb}\n"
            else:
                current_files_context += f"### File: {block['filename']}\n"
                if block.get("is_binary"): current_files_context += f"{block['code']}\n"
                else: current_files_context += f"{bbb}{block.get('language', 'plaintext') or 'plaintext'}\n{block.get('code','')}\n{bbb}\n"
        current_files_context += "\n"

    user_message_with_context = user_message.strip()
    if current_files_context.strip():
         user_message_with_context = user_message_with_context + current_files_context + "Based on the current files above and our chat history, please provide updated file contents using the `### File: ...\n```...\n```\n` format for any files you are creating, modifying, or want to include in the final output. Omit files you want to delete from your response."

    # Use generic chat history format; system prompt is handled by call_llm_api
    generic_api_messages = _convert_gr_history_to_generic_chat_format(_chat_hist[:-1], user_message_with_context)

    _status = f"Waiting for {selected_model_config['ui_name']}..."
    yield (_chat_msg_in, _chat_hist, _status, _detected_files_update, _formatted_output_update, _download_btn_update)

    # For OpenRouter specific headers (example)
    # In a real deployment, this might come from request headers or config
    http_referer = "https://your-app-domain.com" # Or some placeholder if running locally
    http_app_title = "AI Code & Space Generator"

    bot_response_actual, error_msg = call_llm_api(
        selected_model_config,
        generic_api_messages,
        api_key,
        current_sys_prompt,
        BOT_ROLE_NAME, # This is for the AI's response content, not API message roles
        http_referer_url=http_referer,
        http_app_name=http_app_title
    )

    if error_msg: # If call_llm_api returned an error message
        # error_msg is already formatted from call_llm_api
        pass # Will be handled by the final error block below
    elif bot_response_actual:
        _chat_hist[-1] = (user_message, bot_response_actual); _status = "AI response received. Processing files..."
        yield (_chat_msg_in, _chat_hist, _status, _detected_files_update, _formatted_output_update, _download_btn_update)

        latest_bot_message_json = json.dumps([{"role": BOT_ROLE_NAME, "content": bot_response_actual}], indent=2)
        parsing_res = _parse_chat_stream_logic(latest_bot_message_json, existing_files_state=parsed_code_blocks_state_cache)

        if parsing_res["error_message"]:
            _status = f"Parsing Error: {parsing_res['error_message']}"
            _detected_files_update = gr.Markdown(f"## Parsing Error\n`{escape_html_for_markdown(parsing_res['error_message'])}`")
        else:
            _formatted_output_update, _detected_files_update, _download_btn_update = _generate_ui_outputs_from_cache(hf_owner_name, hf_repo_name)
            _status = "Processing complete. Previews updated."
        yield (_chat_msg_in, _chat_hist, _status, _detected_files_update, _formatted_output_update, _download_btn_update); return
    else: # Should not happen if error_msg or bot_response_actual is always set
        error_msg = "Unknown error: No response or error message from LLM call."


    # Common error handling
    if _chat_hist and len(_chat_hist) > 0 and _chat_hist[-1][1] is None:
         _chat_hist[-1] = (_chat_hist[-1][0], error_msg)
    else:
         _chat_hist.append((user_message, error_msg))
    _status = error_msg
    yield (_chat_msg_in, _chat_hist, _status, _detected_files_update, _formatted_output_update, _download_btn_update)


# --- Other handlers (handle_load_existing_space, etc.) remain largely the same ---
# Make sure to pass the correct API keys (e.g., hf_api_key_input) for HF operations
# These functions are for HF Space management, not LLM calls, so less affected by Groq removal.

def handle_load_existing_space(hf_api_key_ui, ui_owner_name, ui_space_name):
    global parsed_code_blocks_state_cache
    _formatted_md_val, _detected_preview_val, _status_val = "*Loading files...*", "*Loading files...*", f"Loading Space: {ui_owner_name}/{ui_space_name}..."
    _file_browser_update, _iframe_html_update, _download_btn_update = gr.update(visible=False, choices=[], value=None), gr.update(value=None, visible=False), gr.update(interactive=False, value=None)
    _build_status_clear, _edit_status_clear, _runtime_status_clear = "*Build status will appear here.*", "*Select a file to load or delete.*", "*Space runtime status will appear here after refresh.*"

    yield (_formatted_md_val, _detected_preview_val, _status_val, _file_browser_update, gr.update(value=ui_owner_name), gr.update(value=ui_space_name), _iframe_html_update, _download_btn_update, _build_status_clear, _edit_status_clear, _runtime_status_clear)

    owner_to_use, updated_owner_name_val = ui_owner_name, ui_owner_name
    error_occurred = False

    if not owner_to_use:
        token, token_err = build_logic_get_api_token(hf_api_key_ui) # Uses HF specific token getter
        if token_err or not token:
            _status_val = f"Error: {token_err or 'Cannot determine owner from token.'}"; error_occurred = True
        else:
            try:
                user_info = build_logic_whoami(token=token)
                if user_info and 'name' in user_info:
                    owner_to_use, updated_owner_name_val = user_info['name'], user_info['name']; _status_val += f" (Auto-detected owner: {owner_to_use})"
                else:
                    _status_val = "Error: Could not auto-detect owner from token."; error_occurred = True
            except Exception as e:
                _status_val = f"Error auto-detecting owner: {e}"; error_occurred = True

    if not owner_to_use or not ui_space_name:
        if not error_occurred: _status_val = "Error: Owner and Space Name are required."; error_occurred = True

    if error_occurred:
         yield (f"*Error: {_status_val}*", f"*Error: {_status_val}*", _status_val, _file_browser_update, updated_owner_name_val, ui_space_name, _iframe_html_update, _download_btn_update, _build_status_clear, _edit_status_clear, _runtime_status_clear)
         return

    sdk_for_iframe, file_list, err_list_files = get_space_repository_info(hf_api_key_ui, ui_space_name, owner_to_use)
    sub_owner = re.sub(r'[^a-z0-9\-]+', '-', owner_to_use.lower()).strip('-') or 'owner'
    sub_repo = re.sub(r'[^a-z0-9\-]+', '-', ui_space_name.lower()).strip('-') or 'space'
    iframe_url = f"https://{sub_owner}-{sub_repo}{'.static.hf.space' if sdk_for_iframe == 'static' else '.hf.space'}"
    _iframe_html_update = gr.update(value=f'<iframe src="{iframe_url}?__theme=light&embed=true" width="100%" height="500px" style="border:1px solid #eee; border-radius:8px;"></iframe>', visible=True)

    if err_list_files and not file_list:
        _status_val = f"File List Error: {err_list_files}"
        parsed_code_blocks_state_cache = []
        _formatted_md_val, _detected_preview_val, _download_btn_update = _generate_ui_outputs_from_cache(owner_to_use, ui_space_name)
        _file_browser_update = gr.update(visible=True, choices=[], value="Error loading files")
        yield (f"*Error: {err_list_files}*", "*Error loading files*", _status_val, _file_browser_update, updated_owner_name_val, ui_space_name, _iframe_html_update, _download_btn_update, _build_status_clear, _edit_status_clear, _runtime_status_clear)
        return

    if not file_list:
        _status_val = f"Loaded Space: {owner_to_use}/{ui_space_name}. No files found ({err_list_files or 'Repository is empty'})."
        parsed_code_blocks_state_cache = []
        _formatted_md_val, _detected_preview_val, _download_btn_update = _generate_ui_outputs_from_cache(owner_to_use, ui_space_name)
        _file_browser_update = gr.update(visible=True, choices=[], value="No files found")
        yield (_formatted_md_val, _detected_preview_val, _status_val, _file_browser_update, updated_owner_name_val, ui_space_name, _iframe_html_update, _download_btn_update, _build_status_clear, _edit_status_clear, _runtime_status_clear)
        return

    loaded_files_for_parse = []
    _status_val = f"Loading {len(file_list)} files from {owner_to_use}/{ui_space_name} (SDK: {sdk_for_iframe or 'unknown'})...";
    yield (_formatted_md_val, _detected_preview_val, _status_val, gr.update(visible=True, choices=sorted(file_list or []), value=None), updated_owner_name_val, ui_space_name, _iframe_html_update, _download_btn_update, _build_status_clear, _edit_status_clear, _runtime_status_clear)

    for file_path in file_list:
        _, ext = os.path.splitext(file_path)
        if ext.lower() in [".png",".jpg",".jpeg",".gif",".ico",".svg",".pt",".bin",".safetensors",".onnx",".woff",".woff2",".ttf",".eot",".zip",".tar",".gz",". هفت",".pdf",".mp4",".avi",".mov",".mp3",".wav",".ogg"] or \
           file_path.startswith(".git") or "/.git/" in file_path or \
           file_path in ["requirements.txt", "environment.yml", "setup.py", "Pipfile", "pyproject.toml", "package.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock"] or \
           file_path.endswith(".lock") or \
           file_path.startswith("__pycache__/") or "/__pycache__/" in file_path or \
           file_path.startswith("node_modules/") or "/node_modules/" in file_path or \
           file_path.startswith("venv/") or "/venv/" in file_path or \
           file_path.startswith(".venv/") or "/.venv/" in file_path:
            loaded_files_for_parse.append({"filename": file_path, "code": "[Binary or Skipped file]", "language": "binary", "is_binary": True, "is_structure_block": False}); continue
        try:
            content, err_get = get_space_file_content(hf_api_key_ui, ui_space_name, owner_to_use, file_path)
            if err_get:
                 loaded_files_for_parse.append({"filename": file_path, "code": f"[Error loading content: {err_get}]", "language": _infer_lang_from_filename(file_path), "is_binary": False, "is_structure_block": False})
                 print(f"Error loading {file_path}: {err_get}");
                 continue
            loaded_files_for_parse.append({"filename": file_path, "code": content, "language": _infer_lang_from_filename(file_path), "is_binary": False, "is_structure_block": False})
        except Exception as content_ex:
            loaded_files_for_parse.append({"filename": file_path, "code": f"[Unexpected error loading content: {content_ex}]", "language": _infer_lang_from_filename(file_path), "is_binary": False, "is_structure_block": False})
            print(f"Unexpected error loading {file_path}: {content_ex}")
            continue

    parsed_code_blocks_state_cache = loaded_files_for_parse
    _formatted_md_val, _detected_preview_val, _download_btn_update = _generate_ui_outputs_from_cache(owner_to_use, ui_space_name)
    _status_val = f"Successfully loaded Space: {owner_to_use}/{ui_space_name}. Markdown ready."
    _file_browser_update = gr.update(visible=True, choices=sorted(file_list or []), value=None)

    yield (_formatted_md_val, _detected_preview_val, _status_val, _file_browser_update, updated_owner_name_val, ui_space_name, _iframe_html_update, _download_btn_update, _build_status_clear, _edit_status_clear, _runtime_status_clear)


def handle_build_space_button(hf_api_key_ui, ui_space_name_part, ui_owner_name_part, space_sdk_ui, formatted_markdown_content):
    _build_status, _iframe_html, _file_browser_update = "Starting space build process...", gr.update(value=None, visible=False), gr.update(visible=False, choices=[], value=None)
    yield _build_status, _iframe_html, _file_browser_update
    if not ui_space_name_part or "/" in ui_space_name_part: _build_status = f"Build Error: HF Space Name '{ui_space_name_part}' must be repo name only (no '/')."; yield _build_status, _iframe_html, _file_browser_update; return
    final_owner_for_build = ui_owner_name_part
    if not final_owner_for_build:
        token_for_whoami, token_err = build_logic_get_api_token(hf_api_key_ui)
        if token_err: _build_status = f"Build Error: {token_err}"; yield _build_status, _iframe_html, _file_browser_update; return
        if token_for_whoami:
            try:
                user_info = build_logic_whoami(token=token_for_whoami)
                final_owner_for_build = user_info['name'] if user_info and 'name' in user_info else final_owner_for_build
                if not final_owner_for_build: _build_status += "\n(Warning: Could not auto-detect owner from token for build. Please specify.)"
            except Exception as e: _build_status += f"\n(Warning: Could not auto-detect owner for build: {e}. Please specify.)"
        else: _build_status += "\n(Warning: Owner not specified and no token to auto-detect for build. Please specify owner or provide a token.)"

    if not final_owner_for_build: _build_status = "Build Error: HF Owner Name could not be determined. Please specify it."; yield _build_status, _iframe_html, _file_browser_update; return

    result_message = build_logic_create_space(hf_api_key_ui, ui_space_name_part, final_owner_for_build, space_sdk_ui, formatted_markdown_content)
    _build_status = f"Build Process: {result_message}"

    if "Successfully" in result_message:
        sub_owner = re.sub(r'[^a-z0-9\-]+', '-', final_owner_for_build.lower()).strip('-') or 'owner'
        sub_repo = re.sub(r'[^a-z0-9\-]+', '-', ui_space_name_part.lower()).strip('-') or 'space'
        iframe_url = f"https://{sub_owner}-{sub_repo}{'.static.hf.space' if space_sdk_ui == 'static' else '.hf.space'}"
        _iframe_html = gr.update(value=f'<iframe src="{iframe_url}?__theme=light&embed=true" width="100%" height="700px" style="border:1px solid #eee; border-radius:8px;"></iframe>', visible=True)
        _build_status += f"\nSpace live at: [Link]({iframe_url}) (Repo: https://huggingface.co/spaces/{final_owner_for_build}/{ui_space_name_part})"
        file_list, err_list = list_space_files_for_browsing(hf_api_key_ui, ui_space_name_part, final_owner_for_build)
        if err_list: _build_status += f"\nFile list refresh error after build: {err_list}"; _file_browser_update = gr.update(visible=True, choices=[], value="Error refreshing files")
        else: _file_browser_update = gr.update(visible=True, choices=sorted(file_list or []), value=None if file_list else "No files found")
    yield _build_status, _iframe_html, _file_browser_update


def handle_load_file_for_editing(hf_api_key_ui, ui_space_name_part, ui_owner_name_part, selected_file_path):
    _file_content_val, _edit_status_val, _commit_msg_val, _lang_update = "", "Error: No file selected.", gr.update(value=""), gr.update(language="python")
    if not selected_file_path or selected_file_path in ["No files found", "Error loading files", "Error refreshing files"]:
         yield _file_content_val, "Select a file from the dropdown.", _commit_msg_val, _lang_update
         return
    owner_to_use = ui_owner_name_part
    if not owner_to_use:
        token, token_err = build_logic_get_api_token(hf_api_key_ui)
        if token_err: _edit_status_val = f"Error: {token_err}"; yield (_file_content_val, _edit_status_val, _commit_msg_val, _lang_update); return
        if token:
            try:
                 user_info = build_logic_whoami(token=token); owner_to_use = user_info['name'] if user_info and 'name' in user_info else owner_to_use
                 if not owner_to_use: _edit_status_val = "Error: Could not auto-detect owner from token."; yield (_file_content_val, _edit_status_val, _commit_msg_val, _lang_update); return
            except Exception as e: _edit_status_val = f"Error auto-detecting owner for editing file: {e}"; yield (_file_content_val, _edit_status_val, _commit_msg_val, _lang_update); return
        else: _edit_status_val = "Error: HF Owner Name not set and no token to auto-detect."; yield (_file_content_val, _edit_status_val, _commit_msg_val, _lang_update); return

    if not owner_to_use or not ui_space_name_part: _edit_status_val = "Error: HF Owner and/or Space Name is missing."; yield (_file_content_val, _edit_status_val, _commit_msg_val, _lang_update); return
    _edit_status_val = f"Loading {selected_file_path}..."
    yield gr.update(value=""), _edit_status_val, gr.update(value=""), gr.update(language="python")
    content, err = get_space_file_content(hf_api_key_ui, ui_space_name_part, owner_to_use, selected_file_path)
    if err:
        _edit_status_val = f"Error loading '{selected_file_path}': {err}"
        _commit_msg_val = f"Error loading {selected_file_path}"
        _file_content_val = f"Error loading {selected_file_path}:\n{err}"
        _lang_update = gr.update(language="python")
        yield _file_content_val, _edit_status_val, _commit_msg_val, _lang_update
        return
    _file_content_val = content or ""
    _edit_status_val = f"Loaded {selected_file_path} for editing."
    _commit_msg_val = f"Update {selected_file_path} via AI Space Editor"
    _lang_update = gr.update(language=_infer_lang_from_filename(selected_file_path))
    yield _file_content_val, _edit_status_val, _commit_msg_val, _lang_update

def handle_commit_file_changes(hf_api_key_ui, ui_space_name_part, ui_owner_name_part, file_to_edit_path, edited_content, commit_message):
    global parsed_code_blocks_state_cache
    _edit_status_val = "Processing commit..."
    _file_browser_update_val = gr.update()
    _formatted_md_out, _detected_preview_out, _download_btn_out = gr.update(), gr.update(), gr.update()
    yield _edit_status_val, _file_browser_update_val, _formatted_md_out, _detected_preview_out, _download_btn_out
    if not file_to_edit_path or file_to_edit_path in ["No files found", "Error loading files", "Error refreshing files"]:
        _edit_status_val = "Error: No valid file selected for commit.";
        yield _edit_status_val, gr.update(), gr.update(), gr.update(), gr.update(); return
    owner_to_use = ui_owner_name_part
    if not owner_to_use:
        token, token_err = build_logic_get_api_token(hf_api_key_ui)
        if token_err: _edit_status_val = f"Error: {token_err}"; yield (_edit_status_val, gr.update(), gr.update(), gr.update(), gr.update()); return
        if token:
            try:
                 user_info = build_logic_whoami(token=token); owner_to_use = user_info['name'] if user_info and 'name' in user_info else owner_to_use
                 if not owner_to_use: _edit_status_val = "Error: Could not auto-detect owner from token."; yield (_edit_status_val, gr.update(), gr.update(), gr.update(), gr.update()); return
            except Exception as e: _edit_status_val = f"Error auto-detecting owner for committing file: {e}"; yield (_edit_status_val, gr.update(), gr.update(), gr.update(), gr.update()); return
        else: _edit_status_val = "Error: HF Owner Name not set and no token to auto-detect."; yield (_edit_status_val, gr.update(), gr.update(), gr.update(), gr.update()); return
    if not owner_to_use or not ui_space_name_part: _edit_status_val = "Error: HF Owner and/or Space Name is missing."; yield (_edit_status_val, gr.update(), gr.update(), gr.update(), gr.update()); return
    status_msg = update_space_file(hf_api_key_ui, ui_space_name_part, owner_to_use, file_to_edit_path, edited_content, commit_message)
    _edit_status_val = status_msg
    if "Successfully updated" in status_msg:
        found_in_cache = False
        for block in parsed_code_blocks_state_cache:
            if block["filename"] == file_to_edit_path:
                block["code"] = edited_content
                block["language"] = _infer_lang_from_filename(file_to_edit_path)
                block["is_binary"] = False
                block["is_structure_block"] = False
                found_in_cache = True
                break
        if not found_in_cache:
             parsed_code_blocks_state_cache.append({
                 "filename": file_to_edit_path, "code": edited_content,
                 "language": _infer_lang_from_filename(file_to_edit_path),
                 "is_binary": False, "is_structure_block": False
             })
             parsed_code_blocks_state_cache.sort(key=lambda b: (0, b["filename"]) if b.get("is_structure_block") else (1, b["filename"]))
        _formatted_md_out, _detected_preview_out, _download_btn_out = _generate_ui_outputs_from_cache(owner_to_use, ui_space_name_part)
        new_file_list, err_list = list_space_files_for_browsing(hf_api_key_ui, ui_space_name_part, owner_to_use)
        if err_list:
             _edit_status_val += f"\nFile list refresh error: {err_list}"
             _file_browser_update_val = gr.update(choices=sorted(new_file_list or []), value="Error refreshing files")
        else:
             _file_browser_update_val = gr.update(choices=sorted(new_file_list or []), value=file_to_edit_path)
    yield _edit_status_val, _file_browser_update_val, _formatted_md_out, _detected_preview_out, _download_btn_out

def handle_delete_file(hf_api_key_ui, ui_space_name_part, ui_owner_name_part, file_to_delete_path):
    global parsed_code_blocks_state_cache
    _edit_status_val = "Processing deletion..."
    _file_browser_choices_update = gr.update()
    _file_browser_value_update = None
    _file_content_editor_update = gr.update(value="")
    _commit_msg_update = gr.update(value="")
    _lang_update = gr.update(language="plaintext")
    _formatted_md_out, _detected_preview_out, _download_btn_out = gr.update(), gr.update(), gr.update()
    yield (_edit_status_val, _file_browser_choices_update, _file_browser_value_update, _file_content_editor_update, _commit_msg_update, _lang_update, _formatted_md_out, _detected_preview_out, _download_btn_out)
    if not file_to_delete_path or file_to_delete_path in ["No files found", "Error loading files", "Error refreshing files"]:
        _edit_status_val = "Error: No valid file selected for deletion.";
        yield (_edit_status_val, gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()); return
    owner_to_use = ui_owner_name_part
    if not owner_to_use:
        token, token_err = build_logic_get_api_token(hf_api_key_ui)
        if token_err: _edit_status_val = f"API Token Error: {token_err}"; yield (_edit_status_val, gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()); return
        if token:
            try:
                 user_info = build_logic_whoami(token=token); owner_to_use = user_info['name'] if user_info and 'name' in user_info else owner_to_use
                 if not owner_to_use: _edit_status_val = "Error: Could not auto-detect owner from token."; yield (_edit_status_val, gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()); return
            except Exception as e: _edit_status_val = f"Error auto-detecting owner for deleting file: {e}"; yield (_edit_status_val, gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()); return
        else: _edit_status_val = "Error: HF Token needed to auto-detect owner."; yield (_edit_status_val, gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()); return
    if not owner_to_use or not ui_space_name_part: _edit_status_val = "Error: Owner and Space Name are required."; yield (_edit_status_val, gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()); return
    deletion_status_msg = build_logic_delete_space_file(hf_api_key_ui, ui_space_name_part, owner_to_use, file_to_delete_path)
    _edit_status_val = deletion_status_msg
    if "Successfully deleted" in deletion_status_msg:
        parsed_code_blocks_state_cache = [b for b in parsed_code_blocks_state_cache if b["filename"] != file_to_delete_path]
        _formatted_md_out, _detected_preview_out, _download_btn_out = _generate_ui_outputs_from_cache(owner_to_use, ui_space_name_part)
        new_file_list, err_list = list_space_files_for_browsing(hf_api_key_ui, ui_space_name_part, owner_to_use)
        if err_list:
             _edit_status_val += f"\nFile list refresh error: {err_list}"
             _file_browser_choices_update = gr.update(choices=sorted(new_file_list or []), value="Error refreshing files")
        else:
             _file_browser_choices_update = gr.update(choices=sorted(new_file_list or []), value=None)
        _file_browser_value_update = None
    else:
        new_file_list, _ = list_space_files_for_browsing(hf_api_key_ui, ui_space_name_part, owner_to_use)
        _file_browser_choices_update = gr.update(choices=sorted(new_file_list or []), value=file_to_delete_path)
        _file_browser_value_update = file_to_delete_path
    yield (_edit_status_val, _file_browser_choices_update, _file_browser_value_update, _file_content_editor_update, _commit_msg_update, _lang_update, _formatted_md_out, _detected_preview_out, _download_btn_out)

def handle_refresh_space_status(hf_api_key_ui, ui_owner_name, ui_space_name):
    yield "*Fetching space status...*"
    owner_to_use = ui_owner_name
    if not owner_to_use:
        token, token_err = build_logic_get_api_token(hf_api_key_ui)
        if token_err or not token: yield f"**Error:** {token_err or 'Cannot determine owner.'}"; return
        try: user_info = build_logic_whoami(token=token); owner_to_use = user_info['name'] if user_info and 'name' in user_info else owner_to_use
        except Exception as e: yield f"**Error auto-detecting owner:** {e}"; return
    if not owner_to_use or not ui_space_name: yield "**Error:** Owner and Space Name are required."; return
    status_details, error_msg = get_space_runtime_status(hf_api_key_ui, ui_space_name, owner_to_use)
    if error_msg: _status_display_md = f"**Error fetching status for {owner_to_use}/{ui_space_name}:**\n\n`{escape_html_for_markdown(error_msg)}`"
    elif status_details:
        stage, hardware, error, log_link = status_details.get('stage','N/A'), status_details.get('hardware','N/A'), status_details.get('error_message'), status_details.get('full_log_link','#')
        md_lines = [f"### Space Status: {owner_to_use}/{ui_space_name}", f"- **Stage:** `{stage}`", f"- **Current Hardware:** `{hardware}`"]
        if status_details.get('requested_hardware') and status_details.get('requested_hardware') != hardware: md_lines.append(f"- **Requested Hardware:** `{status_details.get('requested_hardware')}`")
        if error: md_lines.append(f"- **Error:** <span style='color:red;'>`{escape_html_for_markdown(error)}`</span>")
        md_lines.append(f"- [View Full Logs on Hugging Face]({log_link})")
        if status_details.get('raw_data'):
             md_lines.append(f"\n<details><summary>Raw Status Data (JSON)</summary>\n\n```json\n{json.dumps(status_details.get('raw_data', {}), indent=2)}\n```\n</details>")
        _status_display_md = "\n".join(md_lines)
    else: _status_display_md = "Could not retrieve status details."
    yield _status_display_md

custom_theme = gr.themes.Base(primary_hue="teal", secondary_hue="purple", neutral_hue="zinc", text_size="sm", spacing_size="md", radius_size="sm", font=["System UI", "sans-serif"])
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


with gr.Blocks(theme=custom_theme, css=custom_css) as demo:
    gr.Markdown("# 🤖 AI Code & Space Generator")
    gr.Markdown("Configure settings, chat with AI to generate/modify Hugging Face Spaces, then build, preview, and edit.")
    with gr.Row():
        with gr.Sidebar():
            gr.Markdown("## ⚙️ Configuration")
            with gr.Group():
                gr.Markdown("### API Keys & Tokens")
                # Renamed Groq API key input
                llm_api_key_input = gr.Textbox(label="LLM Provider API Key (Optional)", type="password",
                                               placeholder="Enter key for selected LLM (uses ENV if blank)",
                                               info="Key for the selected LLM provider below. If blank, tries relevant ENV variable.")
                hf_api_key_input = gr.Textbox(label="Hugging Face Token (for Space Ops)", type="password",
                                              placeholder="hf_... (for build/load/edit HF Spaces)")
            with gr.Group():
                gr.Markdown("### Hugging Face Space")
                owner_name_input = gr.Textbox(label="HF Owner Name", placeholder="e.g., your-username")
                space_name_input = gr.Textbox(label="HF Space Name", value="my-ai-space", placeholder="e.g., my-cool-app")
                space_sdk_select = gr.Dropdown(label="Space SDK", choices=["gradio", "streamlit", "docker", "static"], value="gradio", info="Used for new/build.")
                load_space_button = gr.Button("🔄 Load Existing Space", variant="secondary", size="sm")

            with gr.Group():
                gr.Markdown("### AI Model Settings")
                # Model selection from models_config.py
                model_choices_for_ui = [(m["ui_name"], m["ui_name"]) for m in SUPPORTED_MODELS]
                default_model_choice = model_choices_for_ui[0][0] if model_choices_for_ui else None
                llm_model_select = gr.Dropdown(label="Select LLM Model", choices=model_choices_for_ui,
                                               value=default_model_choice,
                                               info="Choose an LLM. Free/trial tier models are listed.")

                system_prompt_input = gr.Textbox(label="System Prompt", lines=8, value=DEFAULT_SYSTEM_PROMPT, interactive=True)

        with gr.Column(scale=3):
            gr.Markdown("## 💬 AI Chat & Code Generation")
            # Updated chatbot display (generic avatar)
            llm_chatbot_display = gr.Chatbot(label="AI Chat", height=400, bubble_full_width=False,
                                             avatar_images=(None, "🤖")) # Generic bot avatar
            with gr.Row():
                llm_chat_message_input = gr.Textbox(show_label=False, placeholder="Your Message...", scale=7)
                llm_send_chat_button = gr.Button("Send", variant="primary", scale=1, size="lg")

            llm_status_output = gr.Textbox(label="Chat/Process Status", interactive=False, lines=1, value="Ready.")
            gr.Markdown("---")
            with gr.Tabs():
                with gr.TabItem("📝 Formatted Space Markdown"):
                    gr.Markdown("Complete Markdown definition for your Space.")
                    formatted_space_output_display = gr.Textbox(label="Current Space Definition", lines=15, interactive=True, show_copy_button=True, value="*Space definition...*")
                    download_button = gr.DownloadButton(label="Download .md", interactive=False, size="sm")
                with gr.TabItem("🔍 Detected Files Preview"):
                    detected_files_preview = gr.Markdown(value="*Files preview...*")
            gr.Markdown("---")
            with gr.Tabs():
                with gr.TabItem("🚀 Build & Preview Space"):
                    with gr.Row():
                        build_space_button = gr.Button("Build / Update Space on HF", variant="primary", scale=2)
                        refresh_status_button = gr.Button("🔄 Refresh Space Status", scale=1)
                    build_status_display = gr.Textbox(label="Build Operation Status", interactive=False, lines=2, value="*Build status will appear here.*")
                    gr.Markdown("---");
                    space_runtime_status_display = gr.Markdown("*Space runtime status will appear here after refresh.*")
                    gr.Markdown("---");
                    space_iframe_display = gr.HTML(value="<!-- Space Iframe -->", visible=False)
                with gr.TabItem("✏️ Edit Space Files"):
                    gr.Markdown("Select a file to view, edit, or delete. Changes are committed to HF Hub.")
                    file_browser_dropdown = gr.Dropdown(label="Select File in Space", choices=[], interactive=True, visible=False, info="Load/build Space first.")
                    file_content_editor = gr.Code(label="File Content Editor", language="python", lines=15, interactive=True)
                    commit_message_input = gr.Textbox(label="Commit Message", placeholder="e.g., Updated app.py", value="Update via AI Space Editor")
                    with gr.Row():
                        update_file_button = gr.Button("Commit Changes", variant="primary", scale=2)
                        delete_file_button = gr.Button("🗑️ Delete Selected File", variant="stop", scale=1)
                    edit_status_display = gr.Textbox(label="File Edit/Delete Status", interactive=False, lines=2, value="*Select file...*")

    # Update chat inputs and outputs to use new component names and function
    chat_outputs = [llm_chat_message_input, llm_chatbot_display, llm_status_output,
                    detected_files_preview, formatted_space_output_display, download_button]
    chat_inputs = [llm_chat_message_input, llm_chatbot_display, llm_api_key_input,
                   llm_model_select, system_prompt_input,
                   owner_name_input, space_name_input, formatted_space_output_display]

    llm_send_chat_button.click(fn=handle_llm_chat_submit, inputs=chat_inputs, outputs=chat_outputs)
    llm_chat_message_input.submit(fn=handle_llm_chat_submit, inputs=chat_inputs, outputs=chat_outputs)

    # Other button clicks remain the same as they primarily use hf_api_key_input for HF operations
    load_space_outputs = [formatted_space_output_display, detected_files_preview, llm_status_output,
                          file_browser_dropdown, owner_name_input, space_name_input,
                          space_iframe_display, download_button, build_status_display,
                          edit_status_display, space_runtime_status_display]
    load_space_button.click(fn=handle_load_existing_space,
                            inputs=[hf_api_key_input, owner_name_input, space_name_input],
                            outputs=load_space_outputs)

    build_outputs = [build_status_display, space_iframe_display, file_browser_dropdown]
    build_space_button.click(fn=handle_build_space_button,
                             inputs=[hf_api_key_input, space_name_input, owner_name_input,
                                     space_sdk_select, formatted_space_output_display],
                             outputs=build_outputs)

    file_edit_load_outputs = [file_content_editor, edit_status_display,
                              commit_message_input, file_content_editor] # file_content_editor for language update
    file_browser_dropdown.change(fn=handle_load_file_for_editing,
                                 inputs=[hf_api_key_input, space_name_input, owner_name_input, file_browser_dropdown],
                                 outputs=file_edit_load_outputs)

    commit_file_outputs = [edit_status_display, file_browser_dropdown,
                           formatted_space_output_display, detected_files_preview, download_button]
    update_file_button.click(fn=handle_commit_file_changes,
                             inputs=[hf_api_key_input, space_name_input, owner_name_input,
                                     file_browser_dropdown, file_content_editor, commit_message_input],
                             outputs=commit_file_outputs)

    delete_file_outputs = [edit_status_display, file_browser_dropdown, file_browser_dropdown, # choices, value
                           file_content_editor, commit_message_input, file_content_editor, # editor, commit, language
                           formatted_space_output_display, detected_files_preview, download_button]
    delete_file_button.click(fn=handle_delete_file,
                             inputs=[hf_api_key_input, space_name_input, owner_name_input, file_browser_dropdown],
                             outputs=delete_file_outputs)

    refresh_status_button.click(fn=handle_refresh_space_status,
                                inputs=[hf_api_key_input, owner_name_input, space_name_input],
                                outputs=[space_runtime_status_display])

if __name__ == "__main__":
    demo.launch(debug=True, share=False)
