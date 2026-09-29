import os
import sys
import time
import json
import glob
import re
import io
import csv
import threading
import queue
from playwright.sync_api import sync_playwright

AUDIO_EXTENSIONS = ('.wav', '.mp3', '.ogg', '.m4a', '.wma')

def generate_voice_name(file_basename, parent_dir, naming_mode="folder_suffix", prefix="", suffix="", pattern=""):
    """
    Generates a Voice Name based on file name, parent folder, and configured rule.
    Supported modes:
      - 'folder_suffix': {file_name}_{parent_dir}
      - 'exact': {file_name}
      - 'prefix': {prefix}{file_name}
      - 'suffix': {file_name}{suffix}
      - 'custom': pattern formatted with {file}, {folder}, {prefix}, {suffix}
    """
    name_without_ext, _ = os.path.splitext(file_basename)
    
    if naming_mode == 'exact':
        return name_without_ext
    elif naming_mode == 'folder_suffix':
        return f"{name_without_ext}_{parent_dir}" if parent_dir else name_without_ext
    elif naming_mode == 'prefix':
        return f"{prefix}{name_without_ext}"
    elif naming_mode == 'suffix':
        return f"{name_without_ext}{suffix}"
    elif naming_mode == 'custom' and pattern:
        res = pattern.replace('{file}', name_without_ext)
        res = res.replace('{folder}', parent_dir)
        res = res.replace('{prefix}', prefix)
        res = res.replace('{suffix}', suffix)
        return res
    else:
        return f"{name_without_ext}_{parent_dir}" if parent_dir else name_without_ext

def scan_voice_files(dir_path, naming_mode="folder_suffix", prefix="", suffix="", pattern=""):
    """
    Scans directory for audio files and generates metadata including proposed voice names.
    Returns (success: bool, result: list | str)
    """
    if not dir_path or not os.path.exists(dir_path):
        return False, f"Directory does not exist: {dir_path}"
    
    if not os.path.isdir(dir_path):
        return False, f"Specified path is not a directory: {dir_path}"

    files_found = []
    for root, _, files in os.walk(dir_path):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in AUDIO_EXTENSIONS:
                full_path = os.path.abspath(os.path.join(root, f))
                parent_dir = os.path.basename(root)
                size_bytes = os.path.getsize(full_path)
                size_mb = round(size_bytes / (1024 * 1024), 2)
                voice_name = generate_voice_name(f, parent_dir, naming_mode, prefix, suffix, pattern)
                
                files_found.append({
                    "path": full_path,
                    "filename": f,
                    "extension": ext,
                    "parent_dir": parent_dir,
                    "size_mb": size_mb,
                    "voice_name": voice_name,
                    "selected": True
                })
    
    files_found.sort(key=lambda x: x["filename"].lower())
    return True, files_found

scan_voice_directory = scan_voice_files

def get_stored_credentials(target_domain=""):
    """
    Checks common credentials.json locations for matching domain username/password.
    """
    cred_candidates = [
        os.path.join(os.getcwd(), ".agent", "credentials.json"),
        r"d:\PlayWright\.agent\credentials.json",
        os.path.expandvars(r"%USERPROFILE%\.gemini\config\credentials.json"),
    ]
    creds = {}
    for c_path in cred_candidates:
        if os.path.exists(c_path):
            try:
                with open(c_path, 'r', encoding='utf-8') as f:
                    creds = json.load(f)
                    break
            except Exception:
                pass

    if target_domain and creds:
        for url_key, acc in creds.items():
            if target_domain.lower() in url_key.lower():
                if acc.get('username') and "your_username_here" not in acc.get('username'):
                    return acc
    return None

def find_cdp_target(custom_cdp_url=None, port=9225):
    """
    Locates active Chrome CDP WebSocket URL or returns HTTP port URL.
    """
    if custom_cdp_url:
        return custom_cdp_url
    
    for dev_path in [
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\DevToolsActivePort"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\AutomationProfile\DevToolsActivePort"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\AutomationDebug\DevToolsActivePort"),
        r"C:\ChromeAutomation\DevToolsActivePort",
        r"C:\ChromeDebug\DevToolsActivePort",
    ]:
        if os.path.exists(dev_path):
            try:
                with open(dev_path, 'r') as f:
                    lines = [l.strip() for l in f.readlines()]
                    if len(lines) >= 2:
                        port_num = lines[0]
                        ws_path = lines[1]
                        return f"ws://127.0.0.1:{port_num}{ws_path}"
            except Exception:
                pass
                
    return f"http://127.0.0.1:{port}"

def normalize_target_voice_url(input_url=None, auth_data=None):
    """
    Given any user-provided URL (e.g. https://tenant.desk-platform.com/entry/manage/agent-roles,
    https://tenant.desk-platform.com/entry/manage/callcenter, tenant.desk-platform.com, or auth_data),
    extracts the domain and normalizes to the Call Center Voice List endpoint.
    """
    raw_url = ""
    if input_url and input_url.strip():
        raw_url = input_url.strip()
    elif auth_data and auth_data.get("base_url"):
        raw_url = auth_data["base_url"].strip()
    else:
        raw_url = "https://tenant.desk-platform.com/entry/manage/callcenter/voice-list"

    if not raw_url.startswith('http://') and not raw_url.startswith('https://'):
        raw_url = f"https://{raw_url}"

    match = re.search(r'https?://([^/]+)', raw_url)
    if match:
        target_domain = match.group(1)
        base_url = f"https://{target_domain}"
    else:
        target_domain = raw_url.replace('https://', '').replace('http://', '').split('/')[0]
        base_url = f"https://{target_domain}"

    # If the user already provided a direct link to the voice list or audio folder, keep it
    if re.search(r'/entry/manage/callcenter/voice-list', raw_url) or re.search(r'/audio-manage', raw_url) or re.search(r'/audio-folder', raw_url):
        target_voice_url = raw_url
    else:
        # For ANY other path (e.g. /entry/manage/agent-roles, /entry/manage/callcenter, /tickets, etc.),
        # directly normalize to the Call Center Voice List endpoint:
        target_voice_url = f"{base_url}/entry/manage/callcenter/voice-list"

    return target_voice_url, target_domain

def upload_voice_stream(files_to_upload, cdp_port=9225, cdp_url=None, target_url=None, auth_data=None, custom_creds=None):
    """
    Generator that performs voice file uploads and yields progress updates as JSON strings.
    Runs Playwright in an isolated thread to guarantee no asyncio loop conflicts.
    """
    q = queue.Queue()

    def send_log(status, message, data=None):
        payload = {"status": status, "message": message}
        if data:
            payload["data"] = data
        return json.dumps(payload, ensure_ascii=False) + "\n"

    def worker():
        if not files_to_upload:
            q.put(send_log("error", "No files selected for upload."))
            q.put(None)
            return

        # Determine target URL and domain flexibly
        url_to_use, target_domain = normalize_target_voice_url(target_url, auth_data)

        q.put(send_log("info", f"Target Domain: {target_domain}"))
        q.put(send_log("info", f"Target Voice URL: {url_to_use}"))
        q.put(send_log("info", f"Queued {len(files_to_upload)} files for upload."))

        browser = None
        is_standalone_browser = False

        try:
            import core.browser
            with sync_playwright() as playwright_instance:
                q.put(send_log("info", "Connecting to shared Chrome browser session..."))
                browser, context, endpoint, was_launched = core.browser.connect_shared_browser(
                    playwright_instance,
                    cdp_port=cdp_port,
                    cdp_url=cdp_url,
                    auth_data=auth_data,
                    target_domain=target_domain
                )

                if was_launched:
                    q.put(send_log("info", f"Auto-launched Chrome on {endpoint} with session initialized."))
                else:
                    q.put(send_log("info", f"Connected to existing Chrome session on {endpoint}."))

                # Step 2: Locate or open target Voice Library page
                target_page, is_new = core.browser.find_or_open_tab(
                    context,
                    url_keywords=["voice-list", "audio", "callcenter"],
                    target_url=url_to_use,
                    auth_data=auth_data,
                    target_domain=target_domain
                )

                page = target_page
                page.bring_to_front()

                # If the tab is on a generic page, navigate it to the voice-list URL
                if "voice-list" not in page.url.lower() and "audio" not in page.url.lower():
                    q.put(send_log("info", f"Navigating tab to Voice List: {url_to_use}..."))
                    page.goto(url_to_use, timeout=45000)
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(3)

                # Step 3: Handle Login if detected
                if "sign_in" in page.url.lower() or "login" in page.url.lower():
                    q.put(send_log("info", "Login page detected. Checking credentials..."))
                    creds = None
                    if custom_creds and custom_creds.get("username") and custom_creds.get("password"):
                        creds = custom_creds
                    else:
                        creds = get_stored_credentials(target_domain)

                    if creds and creds.get("username") and creds.get("password"):
                        q.put(send_log("info", f"Auto-filling credentials for {creds['username']}..."))
                        time.sleep(1)
                        user_input = page.locator("input[type='email'], input[name='user[email]'], input[placeholder*='邮箱']").first
                        if user_input.count() > 0:
                            user_input.fill(creds['username'])
                        pass_input = page.locator("input[type='password'], input[name='user[password]']").first
                        if pass_input.count() > 0:
                            pass_input.fill(creds['password'])
                        login_btn = page.locator("input[type='submit'], button[type='submit'], button:has-text('登录'), button:has-text('Sign In')").first
                        if login_btn.count() > 0:
                            login_btn.click()
                            page.wait_for_load_state("domcontentloaded")
                            time.sleep(4)
                    else:
                        q.put(send_log("info", "Waiting for you to log in in the visible browser window (will auto-resume once logged in)..."))
                        for _ in range(60):
                            if "sign_in" not in page.url.lower() and "login" not in page.url.lower():
                                q.put(send_log("info", "Manual login detected! Resuming..."))
                                break
                            time.sleep(2)

                # Step 4: Ensure Voice File Library Tab is active
                q.put(send_log("info", "Ensuring Voice File Library tab is active..."))
                library_tab = None
                for _ in range(15):
                    for frame in page.frames:
                        loc = frame.locator("a:has-text('Voice File Library'), a[href*='audio-folder'], a:has-text('语音文件库')")
                        if loc.count() > 0:
                            library_tab = loc.first
                            break
                    if library_tab:
                        break
                    time.sleep(1)

                if library_tab:
                    try:
                        q.put(send_log("info", "Switching to 'Voice File Library' tab..."))
                        library_tab.click()
                        time.sleep(3)
                    except Exception as e:
                        q.put(send_log("info", f"Tab switch note: {e}"))

                # Step 5: Upload loop
                total_files = len(files_to_upload)
                success_count = 0
                failed_count = 0

                for idx, item in enumerate(files_to_upload, 1):
                    file_path = item.get("path")
                    voice_name = item.get("voice_name")
                    filename = item.get("filename") or os.path.basename(file_path)

                    if not file_path or not os.path.exists(file_path):
                        failed_count += 1
                        q.put(send_log("error", f"[{idx}/{total_files}] File not found on disk: {file_path}", {"index": idx, "filename": filename, "status": "failed"}))
                        continue

                    q.put(send_log("progress", f"[{idx}/{total_files}] Uploading: '{voice_name}' ({filename})...", {"index": idx, "filename": filename, "status": "uploading"}))

                    # Locate frame containing the upload button with retries
                    target_frame = None
                    for _ in range(15):
                        for frame in page.frames:
                            if frame.locator("button:has-text('Upload voice file'), button:has-text('上传语音文件')").count() > 0:
                                target_frame = frame
                                break
                        if target_frame:
                            break
                        if page.locator("button:has-text('Upload voice file'), button:has-text('上传语音文件')").count() > 0:
                            target_frame = page.main_frame
                            break
                        time.sleep(1)

                    if not target_frame:
                        failed_count += 1
                        q.put(send_log("error", f"[{idx}/{total_files}] Could not find 'Upload voice file' button on page. (Make sure you are in Call Center > Voice Management)", {"index": idx, "filename": filename, "status": "failed"}))
                        continue

                    try:
                        # Click Upload voice file
                        target_frame.locator("button:has-text('Upload voice file'), button:has-text('上传语音文件')").first.click()
                        time.sleep(1.5)

                        # Fill Voice Name
                        name_input = target_frame.locator("label:has-text('Voice Name') + input, input.ccpaas-app-web-input, input[placeholder*='Voice Name'], label:has-text('语音名称') + input")
                        if name_input.count() > 0:
                            name_input.last.fill(voice_name)
                        else:
                            raise Exception("Could not find Voice Name input field.")

                        # Set input file
                        file_input = target_frame.locator("input[type='file']")
                        if file_input.count() > 0:
                            file_input.last.set_input_files(file_path)
                        else:
                            raise Exception("Could not find file input element.")

                        # Wait for file upload processing / OSS progress state
                        time.sleep(2.5)

                        # Check if save button is ready and click Save
                        save_btn = target_frame.locator(".ccpaas-app-web-modal-footer button.ccpaas-app-web-btn-primary, button:has-text('Save'), button:has-text('保存')")
                        if save_btn.count() > 0:
                            save_btn.last.click(force=True)
                        else:
                            raise Exception("Could not find Save button.")

                        # Check for duplicate / error toast messages
                        time.sleep(1.5)
                        error_detected = False
                        error_text = ""
                        
                        error_locators = [
                            target_frame.locator(".ccpaas-app-web-form-explain, .ant-form-explain"),
                            target_frame.locator(".ccpaas-app-web-message-error, .ant-message-error"),
                            page.locator(".ccpaas-app-web-message-error, .ant-message-error")
                        ]
                        for err_loc in error_locators:
                            if err_loc.count() > 0 and err_loc.first.is_visible():
                                error_text = err_loc.first.inner_text().strip()
                                if error_text:
                                    error_detected = True
                                    break

                        if error_detected:
                            cancel_btn = target_frame.locator("button:has-text('Cancel'), button:has-text('取消'), .ccpaas-app-web-modal-close")
                            if cancel_btn.count() > 0:
                                cancel_btn.first.click()
                            time.sleep(1)
                            failed_count += 1
                            q.put(send_log("error", f"[{idx}/{total_files}] Failed to upload '{voice_name}': {error_text}", {"index": idx, "filename": filename, "status": "failed", "error": error_text}))
                            continue

                        # Wait for modal to close
                        try:
                            target_frame.locator(".ccpaas-app-web-modal-wrap").wait_for(state="hidden", timeout=15000)
                        except Exception:
                            cancel_btn = target_frame.locator("button:has-text('Cancel'), button:has-text('取消'), .ccpaas-app-web-modal-close")
                            if cancel_btn.count() > 0 and cancel_btn.first.is_visible():
                                cancel_btn.first.click()

                        success_count += 1
                        q.put(send_log("info", f"[{idx}/{total_files}] Successfully uploaded: '{voice_name}'", {"index": idx, "filename": filename, "status": "success"}))
                        time.sleep(1.5)

                    except Exception as item_err:
                        failed_count += 1
                        try:
                            cancel_btn = target_frame.locator("button:has-text('Cancel'), button:has-text('取消'), .ccpaas-app-web-modal-close")
                            if cancel_btn.count() > 0 and cancel_btn.first.is_visible():
                                cancel_btn.first.click()
                        except Exception:
                            pass
                        q.put(send_log("error", f"[{idx}/{total_files}] Error uploading '{voice_name}': {str(item_err)}", {"index": idx, "filename": filename, "status": "failed", "error": str(item_err)}))
                        time.sleep(1)

                summary_msg = f"Voice upload completed. Total: {total_files} | Succeeded: {success_count} | Failed: {failed_count}"
                q.put(send_log("done", summary_msg, {"total": total_files, "success": success_count, "failed": failed_count}))

        except Exception as e:
            q.put(send_log("error", f"Fatal error in voice upload process: {str(e)}"))
        finally:
            q.put(None)

    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()

    while True:
        chunk = q.get()
        if chunk is None:
            break
        yield chunk


_active_tts_stop_event = None
_tts_lock = threading.Lock()

def get_active_tts_stop_event():
    global _active_tts_stop_event
    return _active_tts_stop_event

def set_active_tts_stop_event(event):
    global _active_tts_stop_event
    with _tts_lock:
        _active_tts_stop_event = event

def request_voice_tts_stop():
    global _active_tts_stop_event
    with _tts_lock:
        if _active_tts_stop_event and not _active_tts_stop_event.is_set():
            _active_tts_stop_event.set()
            return True
        return False

def parse_voice_tts_text(text, default_timbre="小夏"):
    """
    Parses pasted TSV or CSV text into a structured list of voice items.
    Supports:
      - 2 columns: Voice Name \t Voice Content (Timbre defaults to default_timbre)
      - 3 columns: Voice Name \t Voice Content \t Timbre
    Auto-detects and skips header row if present.
    Returns: (success: bool, items: list[dict], message: str)
    """
    if not text or not str(text).strip():
        return False, [], "Input text is empty."

    raw_text = str(text).strip()
    delimiter = '\t' if '\t' in raw_text else ','

    items = []
    lines = raw_text.splitlines()

    reader = csv.reader(io.StringIO(raw_text), delimiter=delimiter)
    all_rows = [row for row in reader if row and any(cell.strip() for cell in row)]

    if not all_rows:
        return False, [], "No valid rows found."

    # Check if first row is header
    first_col = str(all_rows[0][0]).strip().lower()
    header_keywords = ['语音', '名称', 'name', 'title', 'prompt', 'voice', 'filename']
    has_header = any(hk in first_col for hk in header_keywords)
    start_idx = 1 if has_header else 0

    for idx in range(start_idx, len(all_rows)):
        row = all_rows[idx]
        name = str(row[0]).strip() if len(row) > 0 else ""
        content = str(row[1]).strip() if len(row) > 1 else ""
        timbre = str(row[2]).strip() if len(row) > 2 and str(row[2]).strip() else (default_timbre or "小夏")

        if not name and not content:
            continue

        if not name:
            name = f"Voice_{idx+1}"

        items.append({
            "name": name,
            "content": content,
            "timbre": timbre
        })

    if not items:
        return False, [], "No valid voice items extracted from text."

    return True, items, f"Successfully parsed {len(items)} voice items."

TIMBRE_MAP_CN_TO_EN = {
    "小夏": "Little Summer",
    "小雪": "Light Snow",
    "小树": "Little Tree",
    "小明": "Xiaoming",
    "小杰": "Xiaojie",
    "晓晓": "Xiaoxiao",
    "云希": "Yunxi",
    "云野": "Yunye",
    "艾硕": "Ai Shuo🔥",
    "艾悦": "Ai Yue🔥",
    "艾夏": "Aisha🔥",
    "知硕": "Zhishuo🔥",
    "知亚": "Zhiya🔥",
    "知悦": "Zhiyue🔥"
}

def create_voice_tts_stream(voice_items, cdp_port=9225, cdp_url=None, default_timbre="小夏"):
    """
    Automates creating TTS voice files directly on the open '语音列表' (Voice List) tab via Chrome CDP.
    Strictly requires the user to already have the '语音列表' page open in their debug Chrome window.
    Supports both English ('Add voice', 'Audio:', 'TTS', 'Voice') and Chinese UI versions.
    Yields JSON progress events.
    """
    q = queue.Queue()
    stop_event = threading.Event()
    set_active_tts_stop_event(stop_event)

    def send_log(status, message, data=None):
        payload = {"status": status, "message": message}
        if data:
            payload["data"] = data
        return json.dumps(payload, ensure_ascii=False) + "\n"

    def worker():
        if not voice_items or not isinstance(voice_items, list):
            q.put(send_log("error", "No voice items provided for TTS creation."))
            q.put(None)
            return

        total_items = len(voice_items)
        q.put(send_log("info", f"Initiating Batch TTS Voice creation for {total_items} item(s)..."))

        try:
            import core.browser
            with sync_playwright() as playwright_instance:
                q.put(send_log("info", "Connecting to shared Chrome browser session..."))
                browser, context, endpoint, was_launched = core.browser.connect_shared_browser(
                    playwright_instance,
                    cdp_port=cdp_port,
                    cdp_url=cdp_url
                )

                # Strict Tab Matching: Look for active "语音列表" / Voice List tab
                target_page = None
                for p in context.pages:
                    p_url = p.url.lower()
                    if "voice-list" in p_url or "audio" in p_url:
                        target_page = p
                        break

                if not target_page:
                    for p in context.pages:
                        if p.url != "about:blank":
                            try:
                                for f in p.frames:
                                    if f.locator("button:has-text('Add voice'), button:has-text('添加新语音'), button:has-text('Add new voice'), a:has-text('语音文件库'), a:has-text('Voice File Library')").count() > 0:
                                        target_page = p
                                        break
                                if target_page:
                                    break
                            except Exception:
                                pass

                if not target_page:
                    open_urls = [p.url for p in context.pages]
                    q.put(send_log("error", "No open '语音列表' (Voice List) tab found in the debug Chrome window."))
                    q.put(send_log("info", f"Debug Chrome currently sees {len(open_urls)} tab(s): {', '.join(open_urls)}"))
                    q.put(send_log("info", "👉 Please navigate to Call Center > Voice List ('语音列表') in Chrome and try again."))
                    q.put(None)
                    return

                q.put(send_log("info", f"Found active Voice List tab: {target_page.url}"))
                target_page.bring_to_front()
                time.sleep(0.5)

                # Close any pre-existing dangling modal if open
                for f in target_page.frames:
                    try:
                        open_modal = f.locator(".ccpaas-app-web-modal, .ant-modal").first
                        if open_modal.count() > 0 and open_modal.is_visible():
                            c = open_modal.locator(".ccpaas-app-web-modal-close, button:has-text('Cancel'), button:has-text('取消')").first
                            if c.count() > 0 and c.is_visible():
                                c.click()
                                time.sleep(0.5)
                    except Exception:
                        pass

                success_count = 0
                failed_count = 0

                for idx, item in enumerate(voice_items, 1):
                    if stop_event.is_set():
                        q.put(send_log("warn", "Execution stopped by user."))
                        break

                    raw_voice_name = item.get("name", "").strip()
                    # Strictly enforces maxlength=20 on voice name
                    voice_name = raw_voice_name[:20] if raw_voice_name else f"Voice_{idx}"
                    voice_content = item.get("content", "").strip()
                    voice_timbre = item.get("timbre", "").strip() or default_timbre or "小夏"
                    en_timbre = TIMBRE_MAP_CN_TO_EN.get(voice_timbre, voice_timbre)

                    q.put(send_log("progress", f"[{idx}/{total_items}] Creating TTS Voice: '{voice_name}' (Timbre: {voice_timbre})...", {
                        "index": idx,
                        "name": voice_name,
                        "status": "processing"
                    }))

                    # Dismiss any modal leftover before clicking Add
                    for f in target_page.frames:
                        try:
                            leftover = f.locator(".ccpaas-app-web-modal, .ant-modal").first
                            if leftover.count() > 0 and leftover.is_visible():
                                c = leftover.locator(".ccpaas-app-web-modal-close, button:has-text('Cancel'), button:has-text('取消')").first
                                if c.count() > 0 and c.is_visible():
                                    c.click()
                                    time.sleep(0.5)
                        except Exception:
                            pass

                    # Locate "Add voice" / "添加新语音" button with retries
                    add_btn = None
                    target_frame = None
                    for _ in range(10):
                        for f in target_page.frames:
                            loc = f.locator("button:has-text('Add voice'), button:has-text('添加新语音'), button:has-text('添加语音'), button:has-text('Add new voice')")
                            if loc.count() > 0 and loc.first.is_visible():
                                add_btn = loc.first
                                target_frame = f
                                break
                        if add_btn:
                            break
                        if target_page.locator("button:has-text('Add voice'), button:has-text('添加新语音'), button:has-text('添加语音'), button:has-text('Add new voice')").count() > 0:
                            add_btn = target_page.locator("button:has-text('Add voice'), button:has-text('添加新语音'), button:has-text('添加语音'), button:has-text('Add new voice')").first
                            target_frame = target_page.main_frame
                            break
                        time.sleep(1)

                    if not add_btn or not target_frame:
                        failed_count += 1
                        q.put(send_log("error", f"[{idx}/{total_items}] Could not find 'Add voice' / '添加新语音' button on Voice List page.", {
                            "index": idx, "name": voice_name, "status": "failed"
                        }))
                        continue

                    try:
                        # 1. Click "Add voice"
                        add_btn.click()
                        time.sleep(1.2)

                        # Wait for modal
                        modal_wrap = target_frame.locator(".ccpaas-app-web-modal, .ant-modal, div[role='dialog']").first
                        if modal_wrap.count() > 0:
                            modal_wrap.wait_for(state="visible", timeout=8000)

                        # 2. Fill Voice Name (max 20 chars)
                        name_input = modal_wrap.locator(
                            ".form-control-row input.ccpaas-app-web-input, "
                            "label:has-text('Voice Name') + * input, "
                            "label:has-text('语音名称') + * input, "
                            "label:has-text('Voice Name') ~ input, "
                            "label:has-text('语音名称') ~ input, "
                            "input[placeholder*='Voice Name'], "
                            "input[placeholder*='语音名称'], "
                            "input.ccpaas-app-web-input"
                        ).first
                        if name_input.count() > 0:
                            name_input.fill(voice_name)
                        else:
                            raise Exception("Could not find Voice Name input field.")

                        # 3. In Audio / 语音 section, click "+" button
                        plus_btn = modal_wrap.locator(
                            ".unit-plus, "
                            ".anticon-plus-circle, "
                            "span[aria-label='plus-circle'], "
                            ".audio-unit-wrapper .unit-control, "
                            "label:has-text('Audio') ~ * .unit-plus, "
                            "label:has-text('语音') ~ * .unit-plus"
                        ).first

                        if plus_btn.count() > 0:
                            plus_btn.click()
                            time.sleep(1.0)
                        else:
                            raise Exception("Could not find '+' button under Audio / 语音 section.")

                        # 4. First dropdown: Select "TTS" or "文字转语音"
                        type_select = modal_wrap.locator(
                            ".item-input .ccpaas-app-web-select, "
                            ".audio-unit-wrapper .ccpaas-app-web-select, "
                            ".ccpaas-app-web-modal-body .ccpaas-app-web-select"
                        ).first

                        if type_select.count() > 0:
                            tag_name = type_select.evaluate("el => el.tagName.toLowerCase()")
                            if tag_name == "select":
                                type_select.select_option(label="TTS")
                            else:
                                type_select.click()
                                time.sleep(0.5)
                                tts_opt = target_frame.locator(
                                    ".ccpaas-app-web-select-item-option:has-text('TTS'), "
                                    ".ccpaas-app-web-select-item-option:has-text('文字转语音'), "
                                    ".ant-select-item-option:has-text('TTS'), "
                                    ".ant-select-item-option:has-text('文字转语音')"
                                ).first
                                if tts_opt.count() == 0:
                                    tts_opt = target_page.locator(
                                        ".ccpaas-app-web-select-item-option:has-text('TTS'), "
                                        ".ccpaas-app-web-select-item-option:has-text('文字转语音')"
                                    ).first
                                if tts_opt.count() > 0:
                                    tts_opt.click()
                                    time.sleep(0.8)
                                else:
                                    raise Exception("Could not find 'TTS' / '文字转语音' option in dropdown.")

                        # 5. Fill voice prompt content into div[contenteditable="true"]
                        content_editor = modal_wrap.locator("div[contenteditable='true'], .audio-unit-wrapper div[contenteditable='true']").first
                        if content_editor.count() > 0:
                            content_editor.click()
                            content_editor.fill(voice_content)
                            content_editor.evaluate("(el, text) => { el.innerText = text; el.dispatchEvent(new Event('input', { bubbles: true })); }", voice_content)
                        else:
                            # Fallback to textarea
                            ta = modal_wrap.locator(".audio-unit-wrapper textarea, textarea.ccpaas-app-web-input").first
                            if ta.count() > 0:
                                ta.fill(voice_content)
                            else:
                                raise Exception("Could not find content input area for TTS voice script.")

                        # 6. In "Voice" / "声音" dropdown, select timbre
                        timbre_select = modal_wrap.locator(
                            ".tts-config-row .ccpaas-app-web-select, "
                            ".tts-config .ccpaas-app-web-select, "
                            "label:has-text('Voice') ~ * .ccpaas-app-web-select, "
                            "label:has-text('声音') ~ * .ccpaas-app-web-select, "
                            "label:has-text('音色') ~ * .ccpaas-app-web-select"
                        ).first

                        if timbre_select.count() > 0:
                            timbre_select.click()
                            time.sleep(0.5)

                            # Filter via search input scoped to the timbre dropdown
                            search_term = en_timbre.split('🔥')[0].strip()
                            search_inp = timbre_select.locator("input.ccpaas-app-web-select-selection-search-input, input:not([readonly])").first
                            if search_inp.count() > 0 and search_inp.is_visible():
                                try:
                                    search_inp.fill(search_term)
                                    time.sleep(0.5)
                                except Exception:
                                    pass

                            timbre_opt = target_frame.locator(
                                f".ccpaas-app-web-select-item-option:has-text('{en_timbre}'), "
                                f".ccpaas-app-web-select-item-option:has-text('{voice_timbre}'), "
                                f".ccpaas-app-web-select-item-option:has-text('{search_term}'), "
                                f".ant-select-item-option:has-text('{en_timbre}'), "
                                f".ant-select-item-option:has-text('{voice_timbre}'), "
                                f".ant-select-item-option:has-text('{search_term}')"
                            ).first
                            if timbre_opt.count() == 0:
                                timbre_opt = target_page.locator(
                                    f".ccpaas-app-web-select-item-option:has-text('{en_timbre}'), "
                                    f".ccpaas-app-web-select-item-option:has-text('{voice_timbre}'), "
                                    f".ccpaas-app-web-select-item-option:has-text('{search_term}')"
                                ).first

                            if timbre_opt.count() > 0:
                                timbre_opt.click()
                                time.sleep(0.5)
                            else:
                                # Dismiss dropdown if option not directly matched
                                modal_wrap.locator(".ccpaas-app-web-modal-title, .ant-modal-title").first.click(force=True)

                        # 6.5 Click "Synthesize speech" / "合成语音" if present
                        synth_btn = modal_wrap.locator(
                            "span.tts-config-generate:has-text('Synthesize speech'), "
                            "span.tts-config-generate:has-text('合成语音'), "
                            "button:has-text('Synthesize speech'), "
                            "button:has-text('合成语音')"
                        ).first
                        if synth_btn.count() > 0 and synth_btn.is_visible():
                            synth_btn.click()
                            time.sleep(1.5)

                        # 7. Click "Save" / "保存"
                        save_btn = modal_wrap.locator(
                            ".ccpaas-app-web-modal-footer button.ccpaas-app-web-btn-primary, "
                            ".ant-modal-footer button.ant-btn-primary, "
                            "button:has-text('Save'), "
                            "button:has-text('保存')"
                        ).last

                        if save_btn.count() > 0:
                            save_btn.click(force=True)
                        else:
                            raise Exception("Could not find Save button.")

                        # 8. Check for errors
                        time.sleep(1.5)
                        error_detected = False
                        error_text = ""
                        error_locators = [
                            target_frame.locator(".ccpaas-app-web-form-explain, .ant-form-explain"),
                            target_frame.locator(".ccpaas-app-web-message-error, .ant-message-error"),
                            target_page.locator(".ccpaas-app-web-message-error, .ant-message-error")
                        ]
                        for err_loc in error_locators:
                            if err_loc.count() > 0 and err_loc.first.is_visible():
                                txt = err_loc.first.inner_text().strip()
                                if txt:
                                    error_detected = True
                                    error_text = txt
                                    break

                        if error_detected:
                            cancel_btn = modal_wrap.locator("button:has-text('Cancel'), button:has-text('取消'), .ccpaas-app-web-modal-close, .ant-modal-close").first
                            if cancel_btn.count() > 0 and cancel_btn.is_visible():
                                cancel_btn.click()
                            time.sleep(1)
                            failed_count += 1
                            q.put(send_log("error", f"[{idx}/{total_items}] Failed to create '{voice_name}': {error_text}", {
                                "index": idx, "name": voice_name, "status": "failed", "error": error_text
                            }))
                            continue

                        # Wait for modal to hide
                        try:
                            modal_wrap.wait_for(state="hidden", timeout=8000)
                        except Exception:
                            cancel_btn = modal_wrap.locator("button:has-text('Cancel'), button:has-text('取消'), .ccpaas-app-web-modal-close, .ant-modal-close").first
                            if cancel_btn.count() > 0 and cancel_btn.is_visible():
                                cancel_btn.click()

                        success_count += 1
                        q.put(send_log("info", f"[{idx}/{total_items}] Successfully created voice '{voice_name}' ({en_timbre}).", {
                            "index": idx, "name": voice_name, "status": "success"
                        }))

                    except Exception as item_err:
                        failed_count += 1
                        try:
                            cancel_btn = modal_wrap.locator("button:has-text('Cancel'), button:has-text('取消'), .ccpaas-app-web-modal-close, .ant-modal-close").first
                            if cancel_btn.count() > 0 and cancel_btn.is_visible():
                                cancel_btn.click()
                        except Exception:
                            pass
                        q.put(send_log("error", f"[{idx}/{total_items}] Error creating '{voice_name}': {str(item_err)}", {
                            "index": idx, "name": voice_name, "status": "failed", "error": str(item_err)
                        }))

                    # 2-second rate-limiting delay between sequential items
                    if idx < total_items and not stop_event.is_set():
                        time.sleep(2)

                summary_msg = f"Batch TTS creation completed. Total: {total_items} | Succeeded: {success_count} | Failed: {failed_count}"
                q.put(send_log("done", summary_msg, {"total": total_items, "success": success_count, "failed": failed_count}))

        except Exception as e:
            q.put(send_log("error", f"Fatal error in Batch TTS creation: {str(e)}"))
        finally:
            if get_active_tts_stop_event() is stop_event:
                set_active_tts_stop_event(None)
            q.put(None)

    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()

    try:
        while True:
            chunk = q.get()
            if chunk is None:
                break
            yield chunk
    finally:
        stop_event.set()
        if get_active_tts_stop_event() is stop_event:
            set_active_tts_stop_event(None)


