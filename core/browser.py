import os
import sys
import time
import re
import subprocess
import urllib.request
import json
from playwright.sync_api import sync_playwright

COMMON_DEBUG_PORTS = [9225, 9222, 9223, 9333]

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

def is_cdp_port_active(port):
    """Checks if a Chrome DevTools Protocol port is active and responding with /json/version."""
    try:
        url = f"http://127.0.0.1:{port}/json/version"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=1.2) as response:
            return response.status == 200
    except Exception:
        return False

def discover_active_cdp_target(preferred_url=None, preferred_port=9225):
    """
    Finds the active CDP connection string.
    Checks preferred_url first, then preferred_port, then common ports.
    """
    if preferred_url and preferred_url.strip():
        return preferred_url.strip()

    if preferred_port and is_cdp_port_active(preferred_port):
        return f"http://127.0.0.1:{preferred_port}"

    for port in COMMON_DEBUG_PORTS:
        if port != preferred_port and is_cdp_port_active(port):
            return f"http://127.0.0.1:{port}"

    return None

def launch_managed_chrome(port=9225):
    """
    Launches Google Chrome (or Edge) with remote debugging enabled on the specified port.
    """
    chrome_bin = None
    for candidate in CHROME_PATHS:
        if os.path.exists(candidate):
            chrome_bin = candidate
            break

    if not chrome_bin:
        chrome_bin = "chrome.exe"

    user_data_dir = r"C:\ChromeDebug_Ugrator"
    os.makedirs(user_data_dir, exist_ok=True)

    cmd = [
        chrome_bin,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check"
    ]

    try:
        # Launch detached process so it stays alive independently
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'DETACHED_PROCESS', 0x00000008))
    except Exception as e:
        print(f"[BROWSER LAUNCH ERROR] Failed to spawn Chrome: {e}")
        return False

    # Wait up to 6 seconds for CDP listener to become ready
    start_wait = time.time()
    while time.time() - start_wait < 6:
        if is_cdp_port_active(port):
            return True
        time.sleep(0.4)

    return is_cdp_port_active(port)

def inject_auth_cookies(context, auth_data, target_domain=None):
    """
    Injects session cookies from Global Authentication Script into the browser context.
    """
    if not auth_data or not auth_data.get("cookies"):
        return 0

    cookies_dict = auth_data["cookies"]
    if not cookies_dict:
        return 0

    domain = target_domain
    if not domain and auth_data.get("base_url"):
        domain_match = re.search(r'https?://([^/]+)', auth_data["base_url"])
        if domain_match:
            domain = domain_match.group(1)

    if not domain:
        domain = "localhost"

    clean_domain = domain.split(':')[0]
    cookies_to_add = []

    for name, value in cookies_dict.items():
        cookies_to_add.append({
            "name": name,
            "value": str(value),
            "domain": clean_domain,
            "path": "/"
        })

    try:
        context.add_cookies(cookies_to_add)
        return len(cookies_to_add)
    except Exception as e:
        print(f"[COOKIE INJECTION ERROR] {e}")
        return 0

def find_active_canvas_tab(context, url_keywords=None):
    """
    Strict Tab Finder:
    Searches all open tabs in context for an active IVR canvas.
    1. Checks URL matching (e.g. 'callcenter', 'ivr', 'flow-process').
    2. If found, verifies presence of canvas container and brings tab to front.
    3. If no matching tab is found, returns None without opening new URLs.
    """
    keywords = [k.lower() for k in (url_keywords or ["callcenter", "ivr", "flow-process"])]

    for page in context.pages:
        page_url = page.url.lower()
        if any(kw in page_url for kw in keywords):
            page.bring_to_front()
            return page

    # Also inspect DOM across all open non-blank tabs
    for page in context.pages:
        if page.url != "about:blank":
            try:
                for frame in page.frames:
                    if frame.locator(".flow-process-canvas-main-container, #flow-process-canvas-main-container-id, .flow-process-canvas-box").count() > 0:
                        page.bring_to_front()
                        return page
            except Exception:
                pass

    return None

def list_active_canvas_tabs(context, url_keywords=None):
    """
    Scans all open tabs in browser context and returns a list of detected IVR canvas tabs.
    """
    keywords = [k.lower() for k in (url_keywords or ["callcenter", "ivr", "flow-process"])]
    canvas_tabs = []

    for idx, page in enumerate(context.pages):
        page_url = page.url.lower()
        is_canvas = any(kw in page_url for kw in keywords)

        if not is_canvas and page.url != "about:blank":
            try:
                for frame in page.frames:
                    if frame.locator(".flow-process-canvas-main-container, #flow-process-canvas-main-container-id, .flow-process-canvas-box").count() > 0:
                        is_canvas = True
                        break
            except Exception:
                pass

        if is_canvas:
            title = ""
            flow_name = ""
            try:
                title = page.title() or f"IVR Tab {len(canvas_tabs) + 1}"
            except Exception:
                title = f"IVR Tab {len(canvas_tabs) + 1}"

            try:
                for frame in page.frames:
                    name_input = frame.locator("input.flow-process-head-title, input.flow-process-title, .flow-process-name-input")
                    if name_input.count() > 0:
                        val = name_input.first.input_value()
                        if val and val.strip():
                            flow_name = val.strip()
                            break
                    name_text = frame.locator(".ivr-canvas-text, .flow-process-title-text, .flow-name-text")
                    if name_text.count() > 0:
                        txt = name_text.first.inner_text()
                        if txt and txt.strip():
                            flow_name = txt.strip()
                            break
            except Exception:
                pass

            canvas_tabs.append({
                "index": idx,
                "tab_number": len(canvas_tabs) + 1,
                "title": title,
                "url": page.url,
                "flow_name": flow_name or title
            })

    return canvas_tabs

def get_canvas_page_by_index(context, page_index):
    """
    Returns the page at page_index in context.pages and brings it to front.
    Also calls Target.activateTarget via CDP so Chrome physically switches the active tab in the tabstrip.
    """
    if 0 <= page_index < len(context.pages):
        page = context.pages[page_index]
        try:
            page.bring_to_front()
        except Exception:
            pass

        # Physically activate tab in Chrome's UI via CDP
        try:
            cdp = context.new_cdp_session(page)
            targets = cdp.send("Target.getTargets")
            page_targets = [t for t in targets.get("targetInfos", []) if t.get("type") == "page"]
            if 0 <= page_index < len(page_targets):
                cdp.send("Target.activateTarget", {"targetId": page_targets[page_index]["targetId"]})
        except Exception:
            pass

        return page
    return None

def find_or_open_tab(context, url_keywords=None, target_url=None, auth_data=None, target_domain=None):
    """
    Universal Tab Manager:
    Searches existing open tabs in the browser for any matching url_keywords.
    If found, brings it to front and returns the Page object.
    If not found, opens a new tab navigating to target_url.
    """
    keywords = [k.lower() for k in (url_keywords or [])]

    # Check existing open tabs
    for page in context.pages:
        page_url = page.url.lower()
        if any(kw in page_url for kw in keywords):
            page.bring_to_front()
            return page, False

    # No matching tab found -> open new tab
    if auth_data:
        inject_auth_cookies(context, auth_data, target_domain)

    new_page = context.new_page()
    if target_url:
        try:
            new_page.goto(target_url, timeout=30000)
            new_page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
    new_page.bring_to_front()
    return new_page, True

def connect_shared_browser(playwright_instance, cdp_port=9225, cdp_url=None, auth_data=None, target_domain=None):
    """
    Universal Browser Connector:
    1. Connects to existing active Chrome via CDP.
    2. If not running, launches a managed Chrome session and connects.
    3. Injects cookies if auth_data is present.
    Returns (browser, context, cdp_endpoint, was_launched)
    """
    active_target = discover_active_cdp_target(cdp_url, cdp_port)
    was_launched = False

    if not active_target:
        # Chrome is not running with CDP -> automatically launch it!
        target_port = cdp_port or 9225
        launched = launch_managed_chrome(target_port)
        if launched:
            active_target = f"http://127.0.0.1:{target_port}"
            was_launched = True
        else:
            # Fallback to direct Playwright persistent launch
            active_target = None

    if active_target:
        browser = playwright_instance.chromium.connect_over_cdp(active_target)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
    else:
        # Final fallback: launch visible browser
        browser = playwright_instance.chromium.launch(headless=False)
        context = browser.new_context()
        was_launched = True

    if auth_data:
        inject_auth_cookies(context, auth_data, target_domain)

    return browser, context, active_target or "standalone", was_launched
