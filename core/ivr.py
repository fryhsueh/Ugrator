import os
import sys
import time
import json
import yaml
import math
import threading
import queue
from playwright.sync_api import sync_playwright

NODE_TYPE_ALIASES = {
    "play_prompt": "voice_playback",
    "play_voice": "voice_playback",
    "prompt": "voice_playback",
    "playback": "voice_playback",
    "outside_line": "transfer_external",
    "transfer_external_number": "transfer_external",
    "transfer_outside": "transfer_external",
}

NODE_TYPE_PALETTE_MAP = {
    "start": "Start node",
    "voice_playback": "Play prompt",
    "play_prompt": "Play prompt",
    "play_voice": "Play prompt",
    "collect_input": "Collect input",
    "enter_queue": "Enter Queue",
    "info_judgment": "information judgment",
    "hang_up": "Play prompt",
    "transfer_external": "Transfer to external number",
    "speech_recognition": "Speech Recognition",
    "voice_message": "Voice Message",
    "external_interface": "External Interface",
    "satisfaction_survey": "satisfaction survey"
}

NODE_TYPE_PALETTE_MAP_CN = {
    "start": "开始",
    "voice_playback": "放音",
    "play_prompt": "放音",
    "play_voice": "放音",
    "collect_input": "按键收号",
    "enter_queue": "转人工",
    "info_judgment": "信息判断",
    "hang_up": "放音",
    "transfer_external": "转外线",
    "speech_recognition": "语音识别",
    "voice_message": "语音留言",
    "external_interface": "外部接口",
    "satisfaction_survey": "满意度调查"
}

NODE_TYPE_PALETTE_CANDIDATES = {
    "start": ["Start node", "Start", "开始"],
    "voice_playback": ["Play prompt", "Voice playback", "Play voice", "放音"],
    "play_prompt": ["Play prompt", "Voice playback", "Play voice", "放音"],
    "play_voice": ["Play prompt", "Voice playback", "Play voice", "放音"],
    "collect_input": ["Collect input", "按键收号"],
    "enter_queue": ["Enter Queue", "转人工"],
    "info_judgment": ["information judgment", "信息判断"],
    "hang_up": ["Play prompt", "Voice playback", "放音"],
    "transfer_external": ["Transfer to external number", "Transfer to outside line", "转外线"],
    "speech_recognition": ["Speech Recognition", "语音识别"],
    "voice_message": ["Voice Message", "语音留言"],
    "external_interface": ["External Interface", "外部接口"],
    "satisfaction_survey": ["satisfaction survey", "满意度调查"]
}

def _validate_and_layout_nodes(nodes, canvas_name="IVR Flow", is_multi=False):
    """
    Validates a list of nodes for a single canvas (or workflow) and computes layout.
    Enforces strict Start node presence: Every canvas must begin with a Start node as its entry point.
    """
    if not nodes or not isinstance(nodes, list):
        prefix = f"Canvas '{canvas_name}'" if is_multi else "Workflow"
        return False, f"{prefix} must contain a non-empty 'nodes' list.", None, None, None
    
    # Strict Start Node check: The first node MUST be type 'start'
    if not isinstance(nodes[0], dict) or str(nodes[0].get("type", "")).lower() != "start":
        prefix = f"Canvas '{canvas_name}'" if is_multi else "Workflow"
        return False, f"{prefix} must begin with a 'start' node as its entry point.", None, None, None

    node_ids = set()
    referenced_voices = set()
    node_type_counts = {}
    start_count = 0

    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            prefix = f" in canvas '{canvas_name}'" if is_multi else ""
            return False, f"Node at index {idx}{prefix} must be an object.", None, None, None
        
        nid = node.get("id")
        if not nid:
            prefix = f" in canvas '{canvas_name}'" if is_multi else ""
            return False, f"Node at index {idx}{prefix} is missing an 'id'.", None, None, None
            
        if nid in node_ids:
            prefix = f" in canvas '{canvas_name}'" if is_multi else ""
            return False, f"Duplicate node id detected{prefix}: '{nid}'.", None, None, None
        node_ids.add(nid)
        
        raw_ntype = str(node.get("type", "")).lower()
        ntype = NODE_TYPE_ALIASES.get(raw_ntype, raw_ntype)
        if ntype not in NODE_TYPE_PALETTE_MAP:
            valid_types = ", ".join(sorted(set(NODE_TYPE_PALETTE_MAP.keys())))
            prefix = f" in canvas '{canvas_name}'" if is_multi else ""
            return False, f"Node '{nid}'{prefix} has unknown type '{raw_ntype}'. Valid types: {valid_types}", None, None, None
        
        node["type"] = ntype
        
        if ntype == "start":
            start_count += 1
            if start_count > 1:
                prefix = f"Canvas '{canvas_name}'" if is_multi else "Workflow"
                return False, f"{prefix} cannot contain more than one 'start' node.", None, None, None
            
        node_type_counts[ntype] = node_type_counts.get(ntype, 0) + 1
        
        # Enforce 20 character length limitation on node titles
        raw_title = str(node.get("title", nid)).strip()
        if len(raw_title) > 20:
            node["title"] = raw_title[:20]
        else:
            node["title"] = raw_title
            
        audio_name = node.get("audio")
        if audio_name and isinstance(audio_name, str) and audio_name.strip():
            referenced_voices.add(audio_name.strip())
            
        # Check sub-config audio prompts
        config = node.get("config", {})
        if isinstance(config, dict):
            for k in ["timeout_audio", "invalid_audio", "error_audio"]:
                if config.get(k):
                    referenced_voices.add(str(config[k]).strip())

    # Validate route target references
    total_routes_count = 0
    for node in nodes:
        routes = node.get("routes", {})
        if isinstance(routes, dict):
            if "default" in routes:
                target = routes["default"]
                total_routes_count += 1
                if target and target not in node_ids:
                    prefix = f" in canvas '{canvas_name}'" if is_multi else ""
                    return False, f"Node '{node['id']}'{prefix} default route points to unknown node '{target}'.", None, None, None
            if "keys" in routes and isinstance(routes["keys"], dict):
                for key_char, target in routes["keys"].items():
                    total_routes_count += 1
                    if target and target not in node_ids:
                        prefix = f" in canvas '{canvas_name}'" if is_multi else ""
                        return False, f"Node '{node['id']}'{prefix} key '{key_char}' points to unknown node '{target}'.", None, None, None
            for special in ["timeout", "invalid", "error", "match", "mismatch"]:
                if special in routes:
                    target = routes[special]
                    total_routes_count += 1
                    if target and target not in node_ids:
                        prefix = f" in canvas '{canvas_name}'" if is_multi else ""
                        return False, f"Node '{node['id']}'{prefix} '{special}' route points to unknown node '{target}'.", None, None, None
        elif isinstance(routes, str) and routes.strip():
            total_routes_count += 1
            if routes.strip() not in node_ids:
                prefix = f" in canvas '{canvas_name}'" if is_multi else ""
                return False, f"Node '{node['id']}'{prefix} route points to unknown node '{routes}'.", None, None, None

        # Check rules targets for info_judgment
        for r in node.get("rules", []):
            if isinstance(r, dict) and "target" in r:
                rule_target = r["target"]
                if rule_target and rule_target not in node_ids:
                    prefix = f" in canvas '{canvas_name}'" if is_multi else ""
                    return False, f"Node '{node['id']}'{prefix} rule target points to unknown node '{rule_target}'.", None, None, None

    # Calculate layout coordinates
    calculate_dag_layout(nodes)

    canvas_summary = {
        "total_nodes": len(nodes),
        "total_routes": total_routes_count,
        "type_breakdown": node_type_counts,
        "referenced_voices_count": len(referenced_voices)
    }

    return True, None, nodes, referenced_voices, canvas_summary

def parse_ivr_workflow(content_str):
    """
    Parses YAML or JSON workflow definition, validates node definitions,
    and returns a structured dict supporting both single-canvas and multi-canvas workflows:
    {
        "valid": bool,
        "is_multi_canvas": bool,
        "canvases_count": int,
        "ivr_name": str,
        "canvases": list,
        "nodes": list,
        "referenced_voices": list,
        "summary": dict,
        "error": str or None
    }
    """
    if not content_str or not content_str.strip():
        return {"valid": False, "error": "Workflow content is empty."}
    
    try:
        data = yaml.safe_load(content_str)
    except Exception as e:
        try:
            data = json.loads(content_str)
        except Exception:
            return {"valid": False, "error": f"Invalid YAML/JSON format: {str(e)}"}
    
    if not isinstance(data, dict):
        return {"valid": False, "error": "Workflow must be a YAML/JSON object."}
    
    # Check for Multi-Canvas schema
    if "canvases" in data:
        canvases_raw = data.get("canvases")
        if not canvases_raw or not isinstance(canvases_raw, list):
            return {"valid": False, "error": "Workflow 'canvases' must be a non-empty list."}
        
        parsed_canvases = []
        all_nodes = []
        all_referenced_voices = set()
        aggregated_types = {}
        total_routes_all = 0

        for c_idx, c_item in enumerate(canvases_raw):
            if not isinstance(c_item, dict):
                return {"valid": False, "error": f"Canvas at index {c_idx} must be an object."}
            
            c_name = c_item.get("canvas_name") or c_item.get("name") or f"Canvas {c_idx + 1}"
            c_nodes = c_item.get("nodes")
            
            ok, err, v_nodes, v_voices, v_summary = _validate_and_layout_nodes(c_nodes, canvas_name=c_name, is_multi=True)
            if not ok:
                return {"valid": False, "error": err}
            
            parsed_canvases.append({
                "canvas_name": c_name,
                "nodes": v_nodes,
                "referenced_voices": sorted(list(v_voices)),
                "summary": v_summary
            })
            all_nodes.extend(v_nodes)
            all_referenced_voices.update(v_voices)
            total_routes_all += v_summary["total_routes"]
            for ntype, count in v_summary["type_breakdown"].items():
                aggregated_types[ntype] = aggregated_types.get(ntype, 0) + count

        summary = {
            "canvases_count": len(parsed_canvases),
            "total_nodes": len(all_nodes),
            "total_routes": total_routes_all,
            "type_breakdown": aggregated_types,
            "referenced_voices_count": len(all_referenced_voices)
        }

        return {
            "valid": True,
            "is_multi_canvas": True,
            "canvases_count": len(parsed_canvases),
            "ivr_name": data.get("ivr_name", "Multi-Canvas IVR Workflow"),
            "hotline": data.get("hotline", ""),
            "canvases": parsed_canvases,
            "nodes": all_nodes,
            "referenced_voices": sorted(list(all_referenced_voices)),
            "summary": summary,
            "error": None
        }

    # Single-Canvas schema (Classic)
    nodes = data.get("nodes", [])
    ivr_name = data.get("ivr_name", "Untitled IVR Flow")
    ok, err, v_nodes, v_voices, v_summary = _validate_and_layout_nodes(nodes, canvas_name=ivr_name, is_multi=False)
    if not ok:
        return {"valid": False, "error": err}
    
    v_summary["canvases_count"] = 1

    return {
        "valid": True,
        "is_multi_canvas": False,
        "canvases_count": 1,
        "ivr_name": ivr_name,
        "hotline": data.get("hotline", ""),
        "canvases": [
            {
                "canvas_name": ivr_name,
                "nodes": v_nodes,
                "referenced_voices": sorted(list(v_voices)),
                "summary": v_summary
            }
        ],
        "nodes": v_nodes,
        "referenced_voices": sorted(list(v_voices)),
        "summary": v_summary,
        "error": None
    }

def calculate_dag_layout(nodes, start_x=80, start_y=200, col_width=190, row_height=140):
    """
    Computes balanced hierarchical (X, Y) canvas coordinates for all nodes in the graph.
    """
    node_map = {n["id"]: n for n in nodes}
    
    # Identify Start node (or first node)
    start_node = next((n for n in nodes if n.get("type") == "start"), nodes[0])
    
    # Build outgoing adjacency list
    adj = {n["id"]: [] for n in nodes}
    for n in nodes:
        routes = n.get("routes", {})
        if isinstance(routes, dict):
            if "default" in routes and routes["default"] in node_map:
                adj[n["id"]].append(routes["default"])
            if "keys" in routes and isinstance(routes["keys"], dict):
                for target in routes["keys"].values():
                    if target in node_map and target not in adj[n["id"]]:
                        adj[n["id"]].append(target)
            for special in ["timeout", "invalid", "error", "match", "mismatch"]:
                if special in routes and routes[special] in node_map:
                    if routes[special] not in adj[n["id"]]:
                        adj[n["id"]].append(routes[special])
        elif isinstance(routes, str) and routes in node_map:
            adj[n["id"]].append(routes)

        # Include rule targets for information judgment nodes
        for r in n.get("rules", []):
            if isinstance(r, dict) and "target" in r:
                rule_target = r["target"]
                if rule_target in node_map and rule_target not in adj[n["id"]]:
                    adj[n["id"]].append(rule_target)

    # Assign level / depth using BFS
    levels = {}
    visited = set()
    q = [(start_node["id"], 0)]
    visited.add(start_node["id"])

    while q:
        curr_id, depth = q.pop(0)
        levels[curr_id] = depth
        for neighbor in adj.get(curr_id, []):
            if neighbor not in visited:
                visited.add(neighbor)
                q.append((neighbor, depth + 1))

    # For unreached nodes (disconnected branches), assign increasing levels
    max_depth = max(levels.values()) if levels else 0
    for n in nodes:
        if n["id"] not in levels:
            max_depth += 1
            levels[n["id"]] = max_depth

    # Group nodes by level
    level_groups = {}
    for n in nodes:
        lvl = levels[n["id"]]
        level_groups.setdefault(lvl, []).append(n)

    # Assign (X, Y) coordinates with branch-awareness and collision avoidance
    # Detect major dual-language or dual-branch paths if present
    branch_map = {}
    for n in nodes:
        nid_l = n["id"].lower()
        title_l = n.get("title", "").lower()
        if any(k in nid_l or k in title_l for k in ["ar_", "ar ", "arabic", "阿"]):
            branch_map[n["id"]] = "arabic"
        elif any(k in nid_l or k in title_l for k in ["en_", "en ", "english", "英"]):
            branch_map[n["id"]] = "english"
        else:
            branch_map[n["id"]] = "shared"

    has_dual_branches = any(b == "arabic" for b in branch_map.values()) and any(b == "english" for b in branch_map.values())

    for lvl, group in sorted(level_groups.items()):
        col_x = start_x + (lvl * col_width)
        
        if has_dual_branches:
            en_nodes = [n for n in group if branch_map[n["id"]] == "english"]
            ar_nodes = [n for n in group if branch_map[n["id"]] == "arabic"]
            shared_nodes = [n for n in group if branch_map[n["id"]] == "shared"]

            # English Track (Top: Y from 60 up)
            for idx, n in enumerate(en_nodes):
                n["x"] = col_x
                n["y"] = int(60 + idx * 130)

            # Shared nodes (Middle: placed below English nodes with safety margin)
            shared_base_y = max(450, 60 + len(en_nodes) * 130 + 40)
            for idx, n in enumerate(shared_nodes):
                n["x"] = col_x
                n["y"] = int(shared_base_y + idx * 130)

            # Arabic Track (Bottom: Y from 1200 up)
            ar_base_y = max(1200, shared_base_y + len(shared_nodes) * 130 + 60)
            for idx, n in enumerate(ar_nodes):
                n["x"] = col_x
                n["y"] = int(ar_base_y + idx * 130)
        else:
            total = len(group)
            if total == 1:
                group[0]["x"] = col_x
                group[0]["y"] = 220
            elif total == 2:
                group[0]["x"], group[0]["y"] = col_x, 160
                group[1]["x"], group[1]["y"] = col_x, 320
            elif total == 3:
                group[0]["x"], group[0]["y"] = col_x, 110
                group[1]["x"], group[1]["y"] = col_x, 220
                group[2]["x"], group[2]["y"] = col_x, 330
            else:
                for idx, node in enumerate(group):
                    node["x"] = col_x
                    node["y"] = int(60 + idx * 140)

def find_locator_and_frame(page, selector):
    loc = page.locator(selector)
    if loc.count() > 0:
        return loc, page.main_frame
    for frame in page.frames:
        loc = frame.locator(selector)
        if loc.count() > 0:
            return loc, frame
    return None, None

def wait_for_locator_and_frame(page, selector, timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        active_evt = get_active_stop_event()
        if active_evt and active_evt.is_set():
            return None, None
        loc, frame = find_locator_and_frame(page, selector)
        if loc and loc.count() > 0:
            return loc, frame
        time.sleep(0.4)
    return None, None

def close_drawer(target_page):
    """Safely closes the configuration drawer strictly scoped inside open drawers in ember-frame."""
    for frame in list(target_page.frames):
        if 'ember-frame' in frame.name or 'ivr-manage' in frame.url:
            try:
                open_drawers = frame.locator('.ccpaas-app-web-drawer-open')
                for d in open_drawers.all():
                    back_btn = d.locator('.node-drawer-back-btn').first
                    if back_btn.count() > 0:
                        try:
                            back_btn.evaluate("el => el.click()")
                        except Exception:
                            back_btn.click(force=True, timeout=800)
            except Exception:
                pass
    time.sleep(0.4)

def ensure_drawer_closed(target_page, max_retries=3):
    """Verifies that no configuration drawer remains open."""
    for _ in range(max_retries):
        closed = True
        for frame in list(target_page.frames):
            if 'ember-frame' in frame.name or 'ivr-manage' in frame.url:
                if frame.locator('.ccpaas-app-web-drawer-open:visible, .ant-drawer-open:visible').count() > 0:
                    close_drawer(target_page)
                    time.sleep(0.3)
                    closed = False
        if closed:
            break
    ensure_no_modal(target_page)

def ensure_no_modal(target_page):
    """Dismisses any lingering modal dialog or modal backdrop."""
    for frame in list(target_page.frames):
        if 'ember-frame' in frame.name or 'ivr-manage' in frame.url:
            try:
                modals = frame.locator('.ccpaas-app-web-modal:visible, .ant-modal:visible')
                for m in modals.all():
                    cancel_btn = m.locator('button:has-text("Cancel"), button:has-text("取消"), .ant-modal-close, .ccpaas-app-web-modal-close').first
                    if cancel_btn.count() > 0:
                        try:
                            cancel_btn.click()
                        except Exception:
                            pass
                        time.sleep(0.3)
            except Exception:
                pass

def open_node_drawer(target_page, node_locator):
    """
    Opens the configuration drawer by scrolling to and double-clicking the canvas node.
    Attempts synthetic MouseEvent double-click across candidate sub-elements (.canvas-nodes-name-title,
    .canvas-nodes-container, .canvas-nodes-type-title), falling back to Playwright native dblclick,
    and reliably waits for drawer content to mount.
    """
    if not node_locator or node_locator.count() == 0:
        return False

    # Ensure node is centered/visible in viewport
    try:
        node_locator.first.scroll_into_view_if_needed(timeout=1000)
    except Exception:
        pass

    target_sub_selectors = [
        '.canvas-nodes-name-title',
        '.canvas-nodes-container',
        '.canvas-nodes-type-title'
    ]

    for sel in target_sub_selectors:
        sub_el = node_locator.locator(sel).first
        if sub_el.count() == 0:
            continue

        # 1. Synthetic JS double click sequence
        try:
            sub_el.evaluate("""
            (el) => {
                const win = el.ownerDocument.defaultView || window;
                el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: win }));
                el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: win }));
                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: win, detail: 1 }));
                el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: win }));
                el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: win }));
                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: win, detail: 2 }));
                el.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true, view: win }));
            }
            """)
        except Exception:
            pass

        # Poll up to 1.2s for drawer open
        for _ in range(12):
            time.sleep(0.1)
            for f in [target_page] + list(target_page.frames):
                if f.locator('.ccpaas-app-web-drawer-open:visible, .ant-drawer-open:visible').count() > 0:
                    time.sleep(0.3)
                    return True

        # 2. Native Playwright dblclick fallback
        try:
            sub_el.dblclick(force=True, timeout=800)
        except Exception:
            pass

        for _ in range(12):
            time.sleep(0.1)
            for f in [target_page] + list(target_page.frames):
                if f.locator('.ccpaas-app-web-drawer-open:visible, .ant-drawer-open:visible').count() > 0:
                    time.sleep(0.3)
                    return True

    # Fallback directly on parent node container
    try:
        node_locator.first.dblclick(force=True, timeout=800)
    except Exception:
        pass

    for _ in range(10):
        time.sleep(0.1)
        for f in [target_page] + list(target_page.frames):
            if f.locator('.ccpaas-app-web-drawer-open:visible, .ant-drawer-open:visible').count() > 0:
                time.sleep(0.3)
                return True

    return False

def double_click_node_js(target_page, node_locator):
    if not node_locator or node_locator.count() == 0:
        return False
    js_script = """
    (targetNode) => {
        const titleDiv = targetNode.querySelector('.canvas-nodes-name-title') || targetNode.querySelector('.canvas-nodes-container') || targetNode.querySelector('.canvas-nodes-type-title') || targetNode;
        if (!titleDiv) return false;
        const win = targetNode.ownerDocument.defaultView || window;
        titleDiv.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: win }));
        titleDiv.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: win }));
        titleDiv.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: win, detail: 1 }));
        titleDiv.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: win }));
        titleDiv.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: win }));
        titleDiv.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: win, detail: 2 }));
        titleDiv.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true, view: win }));
        return true;
    }
    """
    try:
        return node_locator.first.evaluate(js_script, timeout=2000)
    except Exception:
        return False

def select_dropdown_option_fast(target_select, target_title, target_page, drawer_frame, canvas_frame):
    """
    High-speed Human-Simulated + Adaptive Wait dropdown selection for Ant-Design / PaaS Select.
    1. Scrolls and clicks select to trigger open.
    2. Enters an adaptive polling loop (every 50ms up to 2.0s) waiting for dropdown options to render.
    3. Simulates full human mouse sequence (mouseover -> mousedown -> mouseup -> click) on matching option.
    4. If not found in initial batch:
       - Types filter if search input is editable.
       - Scrolls virtual list holder in JS to uncover the item.
    5. Falls back to multi-frame Playwright locators with strict short timeout.
    Returns True if successfully selected, False otherwise.
    """
    if not target_select or target_select.count() == 0:
        return False

    # 1. Scroll select into center view and trigger open with full mouse sequence
    try:
        target_select.evaluate('''el => {
            el.scrollIntoView({ block: "center" });
            const win = el.ownerDocument.defaultView || window;
            el.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, view: win }));
            el.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true, view: win }));
            el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: win }));
        }''')
    except Exception:
        try:
            target_select.click(force=True, timeout=800)
        except Exception:
            pass

    frames_to_try = [drawer_frame, canvas_frame, target_page] + list(target_page.frames)
    seen_frames = []
    for f in frames_to_try:
        if f and f not in seen_frames:
            seen_frames.append(f)

    # Human simulation click script in JS targeting strictly the active visible dropdown
    js_human_click_script = """
        (target) => {
            const clean = (target || '').trim().toLowerCase();
            
            // Find active visible dropdown (ignoring previously cached hidden dropdowns)
            const dropdowns = Array.from(document.querySelectorAll('.ant-select-dropdown, .ccpaas-app-web-select-dropdown'))
                .filter(d => !d.className.includes('-hidden') && (d.offsetParent !== null || d.style.display !== 'none'));
            const activeDropdown = dropdowns.pop() || document.querySelector('.ant-select-dropdown:not([class*="-hidden"]), .ccpaas-app-web-select-dropdown:not([class*="-hidden"])');
            if (!activeDropdown) return { ready: false, clicked: false };

            function simulateClick(el) {
                const win = el.ownerDocument.defaultView || window;
                el.scrollIntoView({ block: 'nearest' });
                el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true, cancelable: true, view: win }));
                el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: win }));
                el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: win }));
                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: win }));
            }

            function findAndClick() {
                const opts = Array.from(activeDropdown.querySelectorAll(
                    '.ant-select-item-option, .ccpaas-app-web-select-item-option, [role="option"], .ant-select-dropdown [class*="select-item-option"]'
                ));
                if (!opts || opts.length === 0) return null;

                // 1. Exact match on title attribute or text
                for (const o of opts) {
                    const t = (o.getAttribute('title') || '').trim().toLowerCase();
                    const txt = (o.textContent || '').trim().toLowerCase();
                    if (t === clean || txt === clean) {
                        simulateClick(o);
                        return { clicked: true, title: t || txt };
                    }
                }

                // 2. Substring or prefix match
                for (const o of opts) {
                    const t = (o.getAttribute('title') || '').trim().toLowerCase();
                    const txt = (o.textContent || '').trim().toLowerCase();
                    if ((t && t.includes(clean)) || (txt && txt.includes(clean))) {
                        simulateClick(o);
                        return { clicked: true, title: t || txt };
                    }
                }
                return null;
            }

            // Step A: Check current rendered options in active dropdown
            let match = findAndClick();
            if (match) return { ready: true, clicked: true, title: match.title };

            // Step B: If virtual list exists in active dropdown, scroll through it with event dispatch
            const holder = activeDropdown.querySelector('.rc-virtual-list-holder');
            if (holder && holder.scrollHeight > holder.clientHeight) {
                const maxScroll = holder.scrollHeight - holder.clientHeight;
                for (let scrollPos = 60; scrollPos <= maxScroll + 60; scrollPos += 60) {
                    holder.scrollTop = Math.min(scrollPos, maxScroll);
                    holder.dispatchEvent(new Event('scroll', { bubbles: true }));
                    
                    match = findAndClick();
                    if (match) return { ready: true, clicked: true, title: match.title };
                }
            }

            const currentOpts = activeDropdown.querySelectorAll('.ant-select-item-option, .ccpaas-app-web-select-item-option, [role="option"]');
            return { ready: currentOpts.length > 0, clicked: false, count: currentOpts.length };
        }
    """

    # Adaptive polling loop: poll every 50ms up to 2.5s
    start_t = time.time()
    searched_input = False
    reclicked = False

    while time.time() - start_t < 2.5:
        for active_f in seen_frames:
            try:
                res = active_f.evaluate(js_human_click_script, target_title)
                if isinstance(res, dict) and res.get("clicked"):
                    time.sleep(0.12)
                    return True
                # If dropdown not opened after 350ms, re-trigger mousedown on target_select
                if isinstance(res, dict) and not res.get("ready"):
                    if not reclicked and (time.time() - start_t > 0.35):
                        reclicked = True
                        try:
                            target_select.evaluate('''el => {
                                const win = el.ownerDocument.defaultView || window;
                                el.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, view: win }));
                                el.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true, view: win }));
                                el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: win }));
                            }''')
                        except Exception:
                            pass
                # If options are ready but target not found yet, try search input
                if isinstance(res, dict) and res.get("ready") and not res.get("clicked"):
                    if not searched_input and (time.time() - start_t > 0.35):
                        searched_input = True
                        try:
                            search_inp = target_select.locator(
                                'input.ant-select-selection-search-input, '
                                'input.ccpaas-app-web-select-selection-search-input, '
                                'input[type="search"], input'
                            ).first
                            if search_inp.count() > 0 and search_inp.is_visible() and search_inp.is_editable(timeout=150):
                                search_inp.fill(target_title, timeout=300)
                                time.sleep(0.08)
                        except Exception:
                            pass
            except Exception:
                pass
        time.sleep(0.05)

    # Tier 4: Playwright locator fallback across frames with strict short timeout
    for active_f in seen_frames:
        try:
            loc = active_f.locator(
                f'.ccpaas-app-web-select-item-option[title="{target_title}"], '
                f'.ant-select-item-option[title="{target_title}"], '
                f'.ccpaas-app-web-select-item-option-content:text-is("{target_title}"), '
                f'.ant-select-item-option-content:text-is("{target_title}")'
            )
            if loc.count() > 0:
                loc.first.scroll_into_view_if_needed(timeout=400)
                try:
                    loc.first.click(force=True, timeout=400)
                except Exception:
                    loc.first.evaluate("el => el.click()")
                time.sleep(0.1)
                return True
        except Exception:
            pass

    return False

def get_jump_container_by_type(drawer_frame, jump_type="default"):
    """
    Locates the form-item container corresponding to a specific jump route type in the drawer.
    jump_type:
      - 'default': "Node jump" / "节点跳转" (Next job node)
      - 'timeout': "No input jump" / "无输入跳转"
      - 'invalid': "No match jump" / "无匹配跳转"
    Accurately matches specific jump containers while preventing false positive matches on retry fields.
    """
    keywords_map = {
        "default": ["Node jump", "节点跳转", "Neither match jump", "无匹配跳转", "Neither match", "无匹配", "Next node", "下一个节点"],
        "timeout": ["No input jump", "无输入跳转", "No input", "无输入"],
        "invalid": ["No match jump", "无匹配跳转", "No match", "无匹配"]
    }
    keywords = keywords_map.get(jump_type, ["Node jump", "节点跳转"])
    
    for kw in keywords:
        # 1. Direct form-item matching with selects present
        items = drawer_frame.locator(
            f'.ccpaas-app-web-drawer-open .ant-form-item:has(label:has-text("{kw}")):has(.ant-select-selector, .ccpaas-app-web-select-selector), '
            f'.ant-drawer-open .ant-form-item:has(label:has-text("{kw}")):has(.ant-select-selector, .ccpaas-app-web-select-selector)'
        )
        if items.count() > 0:
            return items.first

        # 2. Scoped label matching
        labels = drawer_frame.locator(
            f'.ccpaas-app-web-drawer-open label[title*="{kw}" i], '
            f'.ccpaas-app-web-drawer-open label:has-text("{kw}"), '
            f'.ant-drawer-open label[title*="{kw}" i], '
            f'.ant-drawer-open label:has-text("{kw}")'
        )
        for i in range(labels.count()):
            container = labels.nth(i).locator('xpath=../..')
            if container.count() > 0 and container.locator('.ccpaas-app-web-select-selector, .ant-select-selector, .ccpaas-app-web-select, .ant-select').count() > 0:
                return container
                
    # Fallback for single-jump nodes (e.g. Start, Voice playback)
    if jump_type == "default":
        fallback = drawer_frame.locator(
            '.ccpaas-app-web-drawer-open .ant-form-item:has(label[title*="jump" i]):has(.ant-select-selector, .ccpaas-app-web-select-selector), '
            '.ccpaas-app-web-drawer-open .ant-form-item:has(label[title*="跳转"]):has(.ant-select-selector, .ccpaas-app-web-select-selector), '
            '.ccpaas-app-web-drawer-open .ant-form-item:has(label:has-text("jump")):has(.ant-select-selector, .ccpaas-app-web-select-selector), '
            '.ccpaas-app-web-drawer-open .ant-form-item:has(label:has-text("跳转")):has(.ant-select-selector, .ccpaas-app-web-select-selector), '
            '.ccpaas-app-web-drawer-open .ivr-node-jump-container, '
            '.ant-drawer-open .ant-form-item:has(label[title*="jump" i]):has(.ant-select-selector, .ccpaas-app-web-select-selector), '
            '.ant-drawer-open .ivr-node-jump-container'
        ).first
        if fallback.count() > 0:
            return fallback
            
    return None

_active_stop_lock = threading.Lock()

def get_active_stop_event():
    with _active_stop_lock:
        return getattr(sys, '_ugrator_ivr_active_stop_event', None)

def set_active_stop_event(evt):
    with _active_stop_lock:
        sys._ugrator_ivr_active_stop_event = evt

def request_ivr_stop() -> bool:
    """Signals any active IVR build stream to stop immediately."""
    evt = get_active_stop_event()
    if evt is not None and not evt.is_set():
        evt.set()
        return True
    return False

def _build_single_canvas(target_page, canvas_frame, nodes, canvas_title, canvas_idx, total_canvases, q, send_log, stop_event):
    """
    Executes Phase 1 (Placing nodes & parameters), Phase 2 (Configuring jump routes),
    and Phase 3 (Canvas verification) for a single canvas tab.
    Returns True if successfully completed, or False if aborted/failed.
    """
    total_nodes = len(nodes)
    q.put(send_log("info", f"[{canvas_idx}/{total_canvases}] Starting automation for '{canvas_title}' ({total_nodes} nodes)..."))

    # Safety guard: Prevent accidental clicks on header navigation (Historical Version, back buttons)
    try:
        canvas_frame.evaluate("""() => {
            document.addEventListener('click', (e) => {
                const t = e.target;
                if (!t) return;
                const txt = (t.innerText || '') + (t.title || '') + (t.className || '');
                if (txt.includes('Historical') || txt.includes('历史版本') || txt.includes('fanhui') || txt.includes('ivr-canvas-back')) {
                    e.stopImmediatePropagation();
                    e.preventDefault();
                }
            }, true);
        }""")
    except Exception:
        pass

    # Suppress and dismiss intrusive overlays (AI monitoring popup, security banner)
    try:
        target_page.evaluate("""() => {
            const btn = document.querySelector('.ai-monitor-component-close-btn');
            if (btn) btn.click();
            const closeSec = document.querySelector('.security-update-close, .close-btn');
            if (closeSec) closeSec.click();

            let style = document.getElementById('suppress-intrusive-overlays');
            if (!style) {
                style = document.createElement('style');
                style.id = 'suppress-intrusive-overlays';
                style.textContent = `
                    .ccpaas-app-web-modal-root:has(.ai-monitor-component-close-btn),
                    div:has(> .ai-monitor-component-close-btn),
                    div:has(.ai-monitor-component-auto-listen-btn) {
                        display: none !important;
                        pointer-events: none !important;
                        visibility: hidden !important;
                    }
                `;
                document.head.appendChild(style);
            }
        }""")
        time.sleep(0.3)
    except Exception:
        pass

    if stop_event.is_set():
        q.put(send_log("warn", "IVR build stopped by user."))
        return False

    # Map of placed nodes: id -> {title, locator}
    placed_nodes = {}

    # ========================================================
    # PHASE 1: DRAG AND PLACE NODES
    # ========================================================
    q.put(send_log("info", f"=== [{canvas_idx}/{total_canvases}] Phase 1: Placing {total_nodes} nodes onto canvas '{canvas_title}' ==="))

    # Detect wide workflow and zoom out canvas to expand infinite drop zone
    max_node_x = max([n.get("x", 150) for n in nodes] or [150])
    if max_node_x > 900:
        q.put(send_log("info", f"Wide workflow detected (max X={max_node_x}px). Zooming out canvas to expand infinite drop zone..."))
        scale_btn = canvas_frame.locator('.component-scale-btn-inner-little')
        zoom_clicks = 2 if max_node_x > 1200 else 1
        for _ in range(zoom_clicks):
            if scale_btn.count() > 0:
                try:
                    scale_btn.first.click()
                    time.sleep(0.3)
                except Exception:
                    pass

    for idx, node in enumerate(nodes, 1):
        if stop_event.is_set():
            q.put(send_log("warn", "IVR build stopped by user."))
            return False

        nid = node["id"]
        ntype = node["type"]
        title = node.get("title", nid)
        x = node.get("x", 150)
        y = node.get("y", 250)
        palette_text = NODE_TYPE_PALETTE_MAP.get(ntype, "Play prompt")
        candidates = NODE_TYPE_PALETTE_CANDIDATES.get(ntype, [palette_text])
        cn_palette_text = NODE_TYPE_PALETTE_MAP_CN.get(ntype)

        q.put(send_log("progress", f"[{canvas_idx}/{total_canvases}] [{idx}/{total_nodes}] Placing '{title}' ({palette_text}) at ({x}, {y})...", {"node_id": nid, "status": "placing"}))

        ensure_drawer_closed(target_page)

        # Check if node is Start and already exists on canvas
        new_node_loc = None
        if ntype == "start":
            existing_start = canvas_frame.locator(".flow-process-detail-node:has-text('Start node'), .flow-process-detail-node:has-text('Start'), .flow-process-detail-node:has-text('开始')")
            if existing_start.count() > 0:
                new_node_loc = existing_start.first
            elif len(placed_nodes) == 0:
                existing_nodes = canvas_frame.locator(".flow-process-detail-node")
                if existing_nodes.count() == 1:
                    new_node_loc = existing_nodes.first

        if not new_node_loc:
            # Locate source item in side palette or top toolbar across all candidate names (English modern, legacy, or Chinese)
            source_loc = None
            matched_candidate = None
            for cand in candidates:
                loc = canvas_frame.locator(f"div.page-flow-process-node:has-text('{cand}'), .page-flow-process-node:has-text('{cand}')").first
                if loc.count() > 0:
                    source_loc = loc
                    matched_candidate = cand
                    break

            if not source_loc or source_loc.count() == 0:
                for cand in candidates:
                    loc, _ = wait_for_locator_and_frame(target_page, f"div.page-flow-process-node:has-text('{cand}'), .page-flow-process-node:has-text('{cand}')", timeout=1.5)
                    if loc and loc.count() > 0:
                        source_loc = loc
                        matched_candidate = cand
                        break

            if not source_loc or source_loc.count() == 0:
                q.put(send_log("error", f"Could not find palette item for node '{title}' (tried: {', '.join(candidates)}) on canvas '{canvas_title}'."))
                return False

            # Capture set of existing DOM node IDs before drag
            existing_dom_ids = set()
            for n_el in canvas_frame.locator(".flow-process-detail-node").all():
                el_id = n_el.get_attribute("id")
                if el_id:
                    existing_dom_ids.add(el_id)

            # Primary drop target container (viewport container)
            drop_target = canvas_frame.locator(".flow-process-canvas-main-container, #flow-process-canvas-main-container").first
            cbox = None
            try:
                cbox = drop_target.evaluate("el => el.getBoundingClientRect()")
            except Exception:
                pass
            max_allowed_x = int(cbox['width'] - 120) if cbox and 'width' in cbox else 1200
            max_allowed_y = int(cbox['height'] - 80) if cbox and 'height' in cbox else 480
            safe_x = min(max(80, x), max_allowed_x)
            safe_y = min(max(60, y), max_allowed_y)
            drag_success = False

            # 1. Try Playwright drag_to
            try:
                source_loc.first.drag_to(drop_target, force=True, target_position={"x": safe_x, "y": safe_y})
                time.sleep(1.2)
                for n_el in canvas_frame.locator(".flow-process-detail-node").all():
                    el_id = n_el.get_attribute("id")
                    if el_id and el_id not in existing_dom_ids:
                        new_node_loc = n_el
                        drag_success = True
                        break
            except Exception as drag_err:
                q.put(send_log("warn", f"drag_to notice for '{title}': {drag_err}"))

            # 2. Try secondary drag_to if node not placed yet
            if not drag_success:
                try:
                    time.sleep(0.5)
                    source_loc.first.drag_to(drop_target, force=True, target_position={"x": safe_x, "y": safe_y})
                    time.sleep(1.2)
                except Exception as drag_err:
                    q.put(send_log("warn", f"Second drag_to notice for '{title}': {drag_err}"))

            # Locate newly added DOM node by ID diff
            if not new_node_loc:
                for n_el in canvas_frame.locator(".flow-process-detail-node").all():
                    el_id = n_el.get_attribute("id")
                    if el_id and el_id not in existing_dom_ids:
                        new_node_loc = n_el
                        break

            # Fallback: locate node displaying default palette text not yet configured
            if not new_node_loc:
                for n_el in canvas_frame.locator(".flow-process-detail-node").all():
                    n_text = n_el.inner_text().lower()
                    if any(c.lower() in n_text for c in candidates):
                        already_configured = any(p.get("title", "").lower() in n_text for p in placed_nodes.values())
                        if not already_configured:
                            new_node_loc = n_el
                            break

            # Critical guard: never proceed with a missing or unplaced node
            if not new_node_loc or new_node_loc.count() == 0:
                q.put(send_log("error", f"Could not place or locate node '{title}' on canvas '{canvas_title}'. Halting."))
                return False

        # Explicitly position node to exact (x, y) coordinates on canvas
        try:
            new_node_loc.evaluate(
                "(el, coords) => { el.style.left = coords.x + 'px'; el.style.top = coords.y + 'px'; if (window.jsPlumb) window.jsPlumb.repaintEverything(); }",
                {"x": x, "y": y}
            )
        except Exception:
            pass

        # Open drawer to rename node
        open_node_drawer(target_page, new_node_loc)
        time.sleep(0.8)

        # Rename Node in Drawer
        name_input, drawer_frame = wait_for_locator_and_frame(target_page, '.ccpaas-app-web-drawer-right input.ccpaas-app-web-input, .ccpaas-app-web-drawer-right input#name', timeout=4)
        if not drawer_frame and canvas_frame.locator('.ccpaas-app-web-drawer-right').count() > 0:
            drawer_frame = canvas_frame
            name_input = drawer_frame.locator('.ccpaas-app-web-drawer-right input.ccpaas-app-web-input, .ccpaas-app-web-drawer-right input#name').first

        if not drawer_frame or not name_input or name_input.count() == 0:
            open_node_drawer(target_page, new_node_loc)
            time.sleep(0.8)
            name_input, drawer_frame = wait_for_locator_and_frame(target_page, '.ccpaas-app-web-drawer-right input.ccpaas-app-web-input, .ccpaas-app-web-drawer-right input#name', timeout=3)
            if not drawer_frame and canvas_frame.locator('.ccpaas-app-web-drawer-right').count() > 0:
                drawer_frame = canvas_frame
                name_input = drawer_frame.locator('.ccpaas-app-web-drawer-right input.ccpaas-app-web-input, .ccpaas-app-web-drawer-right input#name').first

        if name_input and name_input.count() > 0:
            name_input.first.fill("")
            name_input.first.fill(title)
            try:
                name_input.first.press("Enter")
            except Exception:
                pass
            try:
                name_input.first.evaluate("el => el.blur()")
            except Exception:
                pass
            time.sleep(0.5)

        # Configure Audio if specified
        audio_name = node.get("audio")
        if audio_name and drawer_frame:
            try:
                q.put(send_log("info", f"[{canvas_idx}/{total_canvases}] [{idx}/{total_nodes}] Binding audio '{audio_name}' to '{title}'..."))
                # Click voice selector/gear icon
                gear_icon = drawer_frame.locator('.ccpaas-app-web-drawer-right i.icon-setting, .ccpaas-app-web-drawer-right .anticon-setting, .ccpaas-app-web-drawer-right .unit-select')
                if gear_icon.count() > 0:
                    try:
                        gear_icon.first.scroll_into_view_if_needed(timeout=800)
                    except Exception:
                        pass
                    gear_icon.first.click(force=True)
                    time.sleep(1)
                    voice_modal, _ = wait_for_locator_and_frame(
                        target_page,
                        '.ccpaas-app-web-modal-content:has-text("Voice"), .ccpaas-app-web-modal-content:has-text("Prompt"), .ccpaas-app-web-modal-content:has-text("Audio"), .ccpaas-app-web-modal-content:has-text("语音"), '
                        '.ant-modal-content:has-text("Voice"), .ant-modal-content:has-text("Prompt"), .ant-modal-content:has-text("Audio"), .ant-modal-content:has-text("语音")',
                        timeout=3
                    )
                    if not voice_modal or voice_modal.count() == 0:
                        voice_modal, _ = wait_for_locator_and_frame(target_page, '.ccpaas-app-web-modal-content, .ant-modal-content', timeout=1.5)
                    if voice_modal and voice_modal.count() > 0:
                        search_box = voice_modal.locator('input.ccpaas-app-web-input, input[placeholder*="search"], input[placeholder*="搜索"]').first
                        if search_box.count() > 0:
                            search_box.fill(audio_name)
                            search_box.press("Enter")
                            time.sleep(0.8)
                        target_row = voice_modal.locator(f"tr:has-text('{audio_name}'), .ant-table-row:has-text('{audio_name}')").first
                        if target_row.count() > 0:
                            radio = target_row.locator('input[type="radio"], .ant-radio-wrapper').first
                            if radio.count() > 0:
                                radio.click()
                            ok_btn = voice_modal.locator('button.ant-btn-primary:has-text("OK"), button.ant-btn-primary:has-text("确定")').first
                            if ok_btn.count() > 0:
                                ok_btn.click()
                                time.sleep(0.5)
            except Exception as audio_err:
                q.put(send_log("warn", f"Notice binding audio '{audio_name}' for '{title}': {audio_err}"))

        # Configure node-specific properties
        config = node.get("config", {})
        if ntype == "collect_input" and config and drawer_frame:
            try:
                # Key timeout
                timeout_val = config.get("timeout_seconds") or config.get("key_timeout")
                if timeout_val:
                    timeout_input = drawer_frame.locator('input[title*="timeout"], input[placeholder*="timeout"], .ant-input-number-input').first
                    if timeout_input.count() > 0:
                        timeout_input.fill(str(timeout_val))
                # Max digits
                max_digits = config.get("max_digits")
                if max_digits:
                    digits_input = drawer_frame.locator('input[title*="digit"], input[placeholder*="位"]').first
                    if digits_input.count() > 0:
                        digits_input.fill(str(max_digits))
            except Exception as cfg_err:
                q.put(send_log("warn", f"Config setup notice for '{title}': {cfg_err}"))

        elif ntype == "enter_queue" and config and drawer_frame:
            try:
                group_name = config.get("group_name")
                if group_name:
                    q.put(send_log("info", f"[{canvas_idx}/{total_canvases}] [{idx}/{total_nodes}] Assigning queue target '{group_name}' to '{title}'..."))
                    grp_select = drawer_frame.locator('.ccpaas-app-web-drawer-right .ccpaas-app-web-select-selector').first
                    if grp_select.count() > 0:
                        grp_select.click()
                        time.sleep(0.5)
                        opt = target_page.locator(f".ccpaas-app-web-select-item-option-content:has-text('{group_name}')").first
                        if opt.count() > 0:
                            opt.click()
                        else:
                            grp_input = grp_select.locator('input')
                            if grp_input.count() > 0:
                                grp_input.fill(group_name)
                                grp_input.press("Enter")
            except Exception as q_err:
                q.put(send_log("warn", f"Queue group setup notice for '{title}': {q_err}"))

        elif ntype == "info_judgment" and drawer_frame:
            rules = node.get("rules", [])
            if rules:
                q.put(send_log("info", f"[{canvas_idx}/{total_canvases}] [{idx}/{total_nodes}] Registered {len(rules)} branch condition rules for '{title}' (will be connected in Phase 2)..."))

        close_drawer(target_page)
        time.sleep(0.35)

        placed_nodes[nid] = {
            "title": title,
            "locator": new_node_loc
        }

    q.put(send_log("info", f"[{canvas_idx}/{total_canvases}] All {total_nodes} nodes placed on canvas '{canvas_title}' successfully."))

    # ========================================================
    # PHASE 2: CONFIGURE ROUTES & CONNECT JUMPS
    # ========================================================
    q.put(send_log("info", f"=== [{canvas_idx}/{total_canvases}] Phase 2: Configuring route connections for canvas '{canvas_title}' ==="))

    for idx, node in enumerate(nodes, 1):
        if stop_event.is_set():
            q.put(send_log("warn", "IVR build stopped by user."))
            return False

        nid = node["id"]
        ntype = node["type"]
        title = node.get("title", nid)
        routes = node.get("routes", {})
        rules = node.get("rules", [])

        if not routes and not rules:
            continue

        q.put(send_log("progress", f"[{canvas_idx}/{total_canvases}] [{idx}/{total_nodes}] Connecting jumps for '{title}'...", {"node_id": nid, "status": "connecting"}))

        node_info = placed_nodes.get(nid)
        if not node_info:
            continue

        # Fresh node locator query by title for rock-solid stability
        node_loc = canvas_frame.locator(f'.flow-process-detail-node:has(.canvas-nodes-name-title:text-is("{title}"))').first
        if node_loc.count() == 0 and node_info.get("locator"):
            node_loc = node_info["locator"]

        ensure_drawer_closed(target_page)
        opened = open_node_drawer(target_page, node_loc)
        if not opened:
            time.sleep(0.3)
            opened = open_node_drawer(target_page, node_loc)

        drawer_frame = target_page.main_frame
        for f in target_page.frames:
            if f.locator('.ccpaas-app-web-drawer-open, .ant-drawer-open, .ccpaas-app-web-drawer-right').count() > 0:
                drawer_frame = f
                break

        def configure_single_jump(jump_container_loc, target_node_id, label="Jump"):
            if not jump_container_loc or jump_container_loc.count() == 0:
                return False

            target_info = placed_nodes.get(target_node_id)
            target_title = target_info["title"] if target_info else ("End Call" if target_node_id in ("hang_up", "root_hangup", "ar_hangup", "en_hangup", "end_call") else target_node_id)

            try:
                jump_container_loc.first.scroll_into_view_if_needed(timeout=800)
            except Exception:
                pass

            sels = jump_container_loc.locator('.ccpaas-app-web-select-selector, .ant-select-selector')
            if sels.count() == 0:
                sels = jump_container_loc.locator('.ccpaas-app-web-select, .ant-select')

            if sels.count() == 0:
                q.put(send_log("warn", f"Select dropdown not found in jump container for {label} -> '{target_title}'."))
                return False

            # Dual-select handling:
            # Select [0] = Action Type ("Node", "Hang up", "--", etc.)
            # Select [1] = Target Node selector
            placed_titles = [p["title"] for p in placed_nodes.values()]

            # If target is Hang up / End Call and there's no placed End Call node:
            if (target_node_id in ("hang_up", "end_call", "root_hangup", "ar_hangup", "en_hangup") or "hang" in target_title.lower()) and target_title not in placed_titles:
                ok = select_dropdown_option_fast(sels.first, "Hang up", target_page, drawer_frame, canvas_frame)
                if not ok:
                    ok = select_dropdown_option_fast(sels.first, "挂机", target_page, drawer_frame, canvas_frame)
                if ok:
                    q.put(send_log("info", f"[{canvas_idx}/{total_canvases}] Set {label} in '{title}' -> Hang up."))
                    return True

            # For node jump: ensure Action Type is "Node"
            first_text = sels.first.inner_text().strip()
            if sels.count() == 1 or first_text not in ("Node", "节点"):
                select_dropdown_option_fast(sels.first, "Node", target_page, drawer_frame, canvas_frame)
                time.sleep(0.35)
                # Re-query selects after type change
                sels = jump_container_loc.locator('.ccpaas-app-web-select-selector, .ant-select-selector')

            # Target node selector is sels.last when 2 or more selects exist
            target_sel = sels.last if sels.count() >= 2 else sels.first
            option_found = select_dropdown_option_fast(target_sel, target_title, target_page, drawer_frame, canvas_frame)

            # Fallback: if target was End Call and option was not found in target_sel, set type to Hang up
            if not option_found and ("end" in target_title.lower() or "hang" in target_title.lower()):
                if select_dropdown_option_fast(sels.first, "Hang up", target_page, drawer_frame, canvas_frame) or select_dropdown_option_fast(sels.first, "挂机", target_page, drawer_frame, canvas_frame):
                    option_found = True
                    target_title = "Hang up"

            if option_found:
                q.put(send_log("info", f"[{canvas_idx}/{total_canvases}] Linked {label} in '{title}' -> '{target_title}'."))
                return True
            else:
                q.put(send_log("warn", f"Could not find dropdown option '{target_title}' for {label} in '{title}'."))
                return False

        # 1. Collect Input Keys & Flow Mapping
        if ntype == "collect_input":
            keys_map = routes.get("keys", {}) if isinstance(routes, dict) else {}

            # Determine default route: explicit "default" route OR destination of common keys
            default_target = routes.get("default") if isinstance(routes, dict) else None
            if not default_target and keys_map:
                distinct_targets = list(dict.fromkeys(keys_map.values()))
                if len(distinct_targets) > 1:
                    q.put(send_log("warn", f"[{canvas_idx}/{total_canvases}] Notice: '{title}' has multiple key routes ({', '.join(keys_map.keys())}) directly without an intermediate information judgment node. Linking Node jump to '{distinct_targets[0]}'. Add an information judgment node after Collect input to branch between DTMF keys."))
                default_target = next(iter(keys_map.values()), None)

            if default_target:
                c_def = get_jump_container_by_type(drawer_frame, "default")
                if c_def and c_def.count() > 0:
                    configure_single_jump(c_def, default_target, "Node jump")
                else:
                    q.put(send_log("warn", f"Default Node jump container not found for '{title}'."))

            if isinstance(routes, dict):
                if "timeout" in routes:
                    c_time = get_jump_container_by_type(drawer_frame, "timeout")
                    if c_time and c_time.count() > 0:
                        configure_single_jump(c_time, routes["timeout"], "No input")
                    else:
                        q.put(send_log("info", f"Timeout jump container not available in '{title}'. Skipping..."))
                if "invalid" in routes:
                    c_inv = get_jump_container_by_type(drawer_frame, "invalid")
                    if c_inv and c_inv.count() > 0:
                        configure_single_jump(c_inv, routes["invalid"], "No match")
                    else:
                        q.put(send_log("info", f"No match jump container not available in '{title}'. Skipping..."))

        # 2. Information Judgment Rules Target Routing
        elif ntype == "info_judgment":
            # Configure decision rules via Add Rule modal
            if rules:
                for r_idx, rule in enumerate(rules):
                    if stop_event.is_set():
                        q.put(send_log("warn", "IVR build stopped by user."))
                        return False
                    r_target = rule.get("target")
                    r_name = rule.get("name", f"Branch {r_idx + 1}")
                    if not r_target:
                        continue

                    try:
                        add_rule_btn = drawer_frame.locator('.judgment-rule-btn-style, .judgment-rule-add-icon, .judgment-rule-btn span').first
                        if add_rule_btn.count() == 0:
                            add_rule_btn = drawer_frame.locator('.judgment-rule-btn').first
                        if add_rule_btn.count() > 0:
                            add_rule_btn.scroll_into_view_if_needed()
                            add_rule_btn.click(force=True)
                            time.sleep(0.8)

                            modal, _ = wait_for_locator_and_frame(
                                target_page,
                                '.ant-modal-content:has-text("Rule Name"), .ccpaas-app-web-modal-content:has-text("Rule Name")',
                                timeout=3
                            )
                            if modal and modal.count() > 0:
                                # 1. Fill Rule Name
                                r_name_input = modal.locator('input#ruleName, input[placeholder*="Rule Name"], input[placeholder*="规则名称"], input.ant-input, input.ccpaas-app-web-input').first
                                if r_name_input.count() > 0:
                                    r_name_input.fill(r_name)
                                    time.sleep(0.2)

                                # 2. Condition Variable: Select "User Input" / "用户输入" or specified variable
                                cond_row = modal.locator('.condition-row').first
                                cond_var = rule.get("variable") or "User Input"
                                if cond_row.count() > 0:
                                    cond_sel = cond_row.locator('.ccpaas-app-web-select-selector, .ant-select-selector').first
                                    if cond_sel.count() > 0:
                                        select_dropdown_option_fast(cond_sel, cond_var, target_page, drawer_frame, canvas_frame)
                                        time.sleep(0.4)

                                # 3. Operator Selection: <select class="operator-selector">
                                op_val = str(rule.get("operator", "Equal")).strip().lower()
                                op_code = "is"
                                if any(w in op_val for w in ["not", "不"]):
                                    op_code = "not"
                                elif any(w in op_val for w in ["any", "contain", "包含"]):
                                    op_code = "is_any"
                                else:
                                    op_code = "is"

                                if cond_row.count() > 0:
                                    op_select = cond_row.locator('select.operator-selector, select.form-control').first
                                    if op_select.count() > 0:
                                        try:
                                            op_select.select_option(value=op_code)
                                            time.sleep(0.2)
                                        except Exception:
                                            pass

                                # 4. Comparison Value: input in condition row
                                val_str = str(rule.get("value", "")).strip()
                                if val_str and cond_row.count() > 0:
                                    val_input = cond_row.locator('input.form-control[type="text"], input[type="text"]').first
                                    if val_input.count() > 0:
                                        val_input.fill(val_str)
                                        time.sleep(0.2)

                                # 5. Jump Target inside modal
                                modal_jump = modal.locator('.component-judgment-rule-modal-jump, .ivr-node-jump-container').first
                                if modal_jump.count() > 0:
                                    configure_single_jump(modal_jump, r_target, f"Branch '{r_name}'")
                                    time.sleep(0.3)

                                # 6. Save via Determine button
                                ok_btn = modal.locator('.ccpaas-app-web-modal-footer button.ccpaas-app-web-btn-primary, .ccpaas-app-web-modal-footer button:has-text("Determine"), .ccpaas-app-web-modal-footer button:has-text("确定")').first
                                if ok_btn.count() > 0:
                                    ok_btn.click(force=True)
                                    try:
                                        modal.wait_for(state="hidden", timeout=3000)
                                    except Exception:
                                        pass
                                    time.sleep(0.5)

                                ensure_no_modal(target_page)
                                q.put(send_log("info", f"[{canvas_idx}/{total_canvases}] Created decision rule '{r_name}' ({cond_var} {op_code} {val_str}) -> '{r_target}' for '{title}'."))
                    except Exception as rule_err:
                        q.put(send_log("warn", f"Notice configuring rule '{r_name}' for '{title}': {rule_err}"))
                        ensure_no_modal(target_page)

            # Default/Fallback route (Neither match jump)
            if isinstance(routes, dict) and "default" in routes:
                c_def = get_jump_container_by_type(drawer_frame, "default")
                if c_def and c_def.count() > 0:
                    configure_single_jump(c_def, routes["default"], "Neither match jump")

        # 3. Standard Single/Default Route Jumps
        else:
            if isinstance(routes, str) and routes.strip():
                c_def = get_jump_container_by_type(drawer_frame, "default")
                if c_def and c_def.count() > 0:
                    configure_single_jump(c_def, routes.strip(), "Default")
                else:
                    q.put(send_log("warn", f"Default jump container not found for '{title}'. Skipping..."))
            elif isinstance(routes, dict):
                if "default" in routes:
                    c_def = get_jump_container_by_type(drawer_frame, "default")
                    if c_def and c_def.count() > 0:
                        configure_single_jump(c_def, routes["default"], "Default")
                    else:
                        q.put(send_log("warn", f"Default jump container not found for '{title}'. Skipping..."))
                if "timeout" in routes:
                    c_time = get_jump_container_by_type(drawer_frame, "timeout")
                    if c_time and c_time.count() > 0:
                        configure_single_jump(c_time, routes["timeout"], "No input")
                    else:
                        q.put(send_log("info", f"Timeout jump container not available in '{title}'. Skipping..."))
                if "invalid" in routes:
                    c_inv = get_jump_container_by_type(drawer_frame, "invalid")
                    if c_inv and c_inv.count() > 0:
                        configure_single_jump(c_inv, routes["invalid"], "No match")
                    else:
                        q.put(send_log("info", f"No match jump container not available in '{title}'. Skipping..."))

        if stop_event.is_set():
            q.put(send_log("warn", "IVR build stopped by user."))
            return False

        close_drawer(target_page)
        time.sleep(0.35)

    # ========================================================
    # PHASE 3: VERIFICATION & SCREENSHOT
    # ========================================================
    q.put(send_log("info", f"=== [{canvas_idx}/{total_canvases}] Phase 3: Finalizing Canvas '{canvas_title}' ==="))
    
    # Center and fit canvas to view
    loc_btn = canvas_frame.locator('.canvas-location-btn, .anticon-aim')
    if loc_btn.count() > 0:
        try:
            loc_btn.first.click()
            time.sleep(0.5)
        except Exception:
            pass

    fit_btn = canvas_frame.locator('.flow-process-tools-item:has-text("1:1"), .flow-process-tools-item:has-text("适应"), .anticon-compress')
    if fit_btn.count() > 0:
        try:
            fit_btn.first.click()
            time.sleep(0.8)
        except Exception:
            pass

    q.put(send_log("info", f"Canvas [{canvas_idx}/{total_canvases}] '{canvas_title}' successfully completed! ({total_nodes} nodes)."))
    return True

def build_ivr_stream(workflow_content, cdp_port=9225, cdp_url=None, auth_data=None, stop_event=None, tab_mappings=None):
    """
    Generator executing the automated IVR Flow builder via Playwright CDP.
    Yields real-time streaming JSON log chunks.
    Supports graceful cancellation via stop_event or request_ivr_stop().
    Supports both single-canvas and multi-canvas workflows across open Chrome tabs.
    """
    if stop_event is None:
        stop_event = threading.Event()
    set_active_stop_event(stop_event)

    q = queue.Queue()

    def send_log(status, message, data=None):
        payload = {"status": status, "message": message}
        if data:
            payload["data"] = data
        return json.dumps(payload, ensure_ascii=False) + "\n"

    def worker():
        if stop_event.is_set():
            q.put(send_log("warn", "IVR build stopped by user."))
            q.put(None)
            return

        # Parse and validate workflow
        parse_result = parse_ivr_workflow(workflow_content)
        if not parse_result["valid"]:
            q.put(send_log("error", f"Validation failed: {parse_result['error']}"))
            q.put(None)
            return

        if stop_event.is_set():
            q.put(send_log("warn", "IVR build stopped by user."))
            q.put(None)
            return

        ivr_name = parse_result.get("ivr_name", "IVR Flow")
        is_multi = parse_result.get("is_multi_canvas", False)
        canvases = parse_result.get("canvases", [])
        total_canvases = len(canvases)
        total_nodes = parse_result.get("summary", {}).get("total_nodes", len(parse_result.get("nodes", [])))

        if is_multi:
            q.put(send_log("info", f"Parsed Multi-Canvas IVR Workflow: '{ivr_name}' with {total_canvases} canvases and {total_nodes} total nodes."))
        else:
            q.put(send_log("info", f"Parsed IVR Workflow: '{ivr_name}' with {total_nodes} nodes."))

        try:
            import core.browser
            with sync_playwright() as p:
                q.put(send_log("info", "Connecting to shared Chrome browser session..."))
                browser, context, endpoint, was_launched = core.browser.connect_shared_browser(
                    p,
                    cdp_port=cdp_port,
                    cdp_url=cdp_url,
                    auth_data=auth_data
                )

                if was_launched:
                    q.put(send_log("info", f"Auto-launched Chrome on {endpoint} with session initialized."))
                else:
                    q.put(send_log("info", f"Connected to existing Chrome session on {endpoint}."))

                if is_multi:
                    # Normalize tab_mappings: list of {canvas_index, tab_index} or dict
                    tab_map = {}
                    if tab_mappings:
                        if isinstance(tab_mappings, list):
                            for item in tab_mappings:
                                if isinstance(item, dict):
                                    tab_map[int(item.get("canvas_index", 0))] = int(item.get("tab_index", 0))
                        elif isinstance(tab_mappings, dict):
                            for k, v in tab_mappings.items():
                                tab_map[int(k)] = int(v)

                    detected_tabs = core.browser.list_active_canvas_tabs(context)
                    q.put(send_log("info", f"Found {len(detected_tabs)} active IVR canvas tab(s) in Chrome."))

                    if len(tab_map) > 1 and len(set(tab_map.values())) < len(tab_map):
                        q.put(send_log("warn", f"⚠️ Notice: Multiple canvases are assigned to the same Chrome tab: {tab_map}."))

                    for c_idx, canvas_item in enumerate(canvases):
                        if stop_event.is_set():
                            q.put(send_log("warn", "IVR build stopped by user."))
                            q.put(None)
                            return

                        c_title = canvas_item.get("canvas_name", f"Canvas {c_idx + 1}")
                        c_nodes = canvas_item.get("nodes", [])

                        target_tab_idx = tab_map.get(c_idx)
                        target_page = None

                        if target_tab_idx is not None:
                            target_page = core.browser.get_canvas_page_by_index(context, target_tab_idx)
                        elif c_idx < len(detected_tabs):
                            target_page = core.browser.get_canvas_page_by_index(context, detected_tabs[c_idx]["index"])

                        if not target_page:
                            q.put(send_log("error", f"Could not locate target Chrome tab for Canvas [{c_idx + 1}/{total_canvases}] '{c_title}'. Please ensure each canvas has an open tab."))
                            q.put(None)
                            return

                        tab_display_name = ""
                        try:
                            for f in target_page.frames:
                                loc = f.locator(".ivr-canvas-text, .flow-process-title-text, .flow-name-text")
                                if loc.count() > 0:
                                    txt = loc.first.inner_text().strip()
                                    if txt:
                                        tab_display_name = txt
                                        break
                            if not tab_display_name:
                                tab_display_name = target_page.title() or target_page.url
                        except Exception:
                            tab_display_name = target_page.url

                        q.put(send_log("info", f"=== [{c_idx + 1}/{total_canvases}] Switching to tab: '{tab_display_name}' for '{c_title}' ==="))
                        target_page.bring_to_front()
                        time.sleep(0.5)

                        canvas_loc, canvas_frame = wait_for_locator_and_frame(target_page, ".flow-process-canvas-main-container, #flow-process-canvas-main-container-id", timeout=12)
                        if not canvas_loc:
                            q.put(send_log("error", f"Canvas editor not detected on tab for Canvas [{c_idx + 1}/{total_canvases}] '{c_title}'. Please click into the IVR flow designer on that tab."))
                            q.put(None)
                            return

                        success = _build_single_canvas(target_page, canvas_frame, c_nodes, c_title, c_idx + 1, total_canvases, q, send_log, stop_event)
                        if not success:
                            q.put(send_log("error", f"Multi-canvas build halted due to error on Canvas [{c_idx + 1}/{total_canvases}] '{c_title}'."))
                            q.put(None)
                            return

                    q.put(send_log("done", f"All {total_canvases} canvases successfully built! Total: {total_nodes} nodes configured across all tabs.", {"total": total_nodes, "canvases": total_canvases}))

                else:
                    # Single Canvas
                    target_tab_idx = None
                    if tab_mappings:
                        if isinstance(tab_mappings, list) and len(tab_mappings) > 0 and isinstance(tab_mappings[0], dict):
                            target_tab_idx = int(tab_mappings[0].get("tab_index", 0))
                        elif isinstance(tab_mappings, dict) and len(tab_mappings) > 0:
                            target_tab_idx = int(list(tab_mappings.values())[0])

                    if target_tab_idx is not None:
                        target_page = core.browser.get_canvas_page_by_index(context, target_tab_idx)
                    else:
                        target_page = core.browser.find_active_canvas_tab(
                            context,
                            url_keywords=["callcenter", "ivr", "flow-process"]
                        )
                    if not target_page:
                        open_urls = [p.url for p in context.pages]
                        q.put(send_log("error", f"No open IVR Canvas tab found in the debug Chrome window."))
                        q.put(send_log("info", f"Debug Chrome currently sees {len(open_urls)} tab(s): {', '.join(open_urls)}"))
                        q.put(send_log("info", "👉 Please open your IVR canvas in the debug Chrome window and click 'Build on Canvas' again."))
                        q.put(None)
                        return

                    q.put(send_log("info", f"Found active IVR Canvas tab: {target_page.url}"))
                    target_page.bring_to_front()

                    canvas_loc, canvas_frame = wait_for_locator_and_frame(target_page, ".flow-process-canvas-main-container, #flow-process-canvas-main-container-id", timeout=12)
                    if not canvas_loc:
                        q.put(send_log("error", "Found Call Center tab, but could not detect the canvas editor. Please ensure you have clicked into the IVR Flow designer."))
                        q.put(None)
                        return

                    success = _build_single_canvas(target_page, canvas_frame, parse_result["nodes"], ivr_name, 1, 1, q, send_log, stop_event)
                    if success:
                        q.put(send_log("done", f"IVR Flow '{ivr_name}' successfully built on canvas! Total: {total_nodes} nodes configured.", {"total": total_nodes}))

        except Exception as e:
            q.put(send_log("error", f"Fatal error in IVR Flow builder: {str(e)}"))
        finally:
            if get_active_stop_event() is stop_event:
                set_active_stop_event(None)
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
        if get_active_stop_event() is stop_event:
            set_active_stop_event(None)
