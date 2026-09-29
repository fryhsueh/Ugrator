import sys
import os
import json
import base64
import importlib
import core.auth
import core.fields
import core.templates
import core.groups
import core.assign
import core.voice
import core.ivr
import core.browser
import core.agents

ALL_MODULES = [
    core.auth,
    core.fields,
    core.templates,
    core.groups,
    core.assign,
    core.agents,
    core.voice,
    core.ivr,
    core.browser
]

def reload_all():
    """
    Dynamically reloads all business and routing modules on every F5 / API call.
    """
    is_building = core.ivr.get_active_stop_event() is not None
    for mod in ALL_MODULES:
        if is_building and mod is core.ivr:
            continue
        try:
            importlib.reload(mod)
        except Exception as e:
            print(f"[RELOAD ERROR] Could not reload {mod.__name__}: {e}")

def send_json(handler, status_code, payload):
    handler.send_response(status_code)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.end_headers()
    handler.wfile.write(json.dumps(payload, ensure_ascii=False).encode('utf-8'))

def dispatch_get(handler):
    """
    Handles specific GET API endpoints before falling back to static file serving.
    Returns True if handled, False otherwise.
    """
    path = handler.path.split('?')[0]
    if path == '/api/download-custom-fields-template':
        template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates', 'custom_fields_template.xlsx')
        if not os.path.exists(template_path):
            send_json(handler, 404, {"success": False, "message": "Template file not found."})
            return True
        try:
            with open(template_path, 'rb') as f:
                content = f.read()
            handler.send_response(200)
            handler.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            handler.send_header('Content-Disposition', 'attachment; filename="custom_fields_template.xlsx"')
            handler.send_header('Content-Length', str(len(content)))
            handler.end_headers()
            handler.wfile.write(content)
            return True
        except Exception as e:
            send_json(handler, 500, {"success": False, "message": str(e)})
            return True
    return False

def dispatch_post(handler):
    """
    Dynamically routes all POST /api/* endpoints.
    Adding or modifying any endpoint here takes effect immediately on the next request without server restart!
    """
    path = handler.path

    if path == '/api/validate-ivr':
        handle_validate_ivr(handler)
    elif path == '/api/list-ivr-tabs':
        handle_list_ivr_tabs(handler)
    elif path == '/api/build-ivr':
        handle_build_ivr(handler)
    elif path == '/api/stop-ivr':
        handle_stop_ivr(handler)
    elif path == '/api/fetch-custom-fields':
        handle_fetch_custom_fields(handler, default_owner="Ticket")
    elif path == '/api/fetch-customer-fields':
        handle_fetch_customer_fields(handler)
    elif path == '/api/create-custom-fields':
        handle_create_custom_fields(handler, default_owner="Ticket")
    elif path == '/api/create-customer-fields':
        handle_create_customer_fields(handler)
    elif path == '/api/parse-custom-fields-file':
        handle_parse_custom_fields_file(handler)
    elif path == '/api/migrate-fields':
        handle_migrate_fields(handler)
    elif path == '/api/migrate-template':
        handle_migrate_template(handler)
    elif path == '/api/create-agent-groups':
        handle_create_agent_groups(handler)
    elif path == '/api/fetch-agent-metadata':
        handle_fetch_agent_metadata(handler)
    elif path == '/api/create-agents':
        handle_create_agents(handler)
    elif path == '/api/parse-agents-file':
        handle_parse_agents_file(handler)
    elif path == '/api/assign-agents':
        handle_assign_agents(handler)
    elif path in ('/api/fetch-tenant-data', '/api/fetch-platform-data'):
        handle_fetch_tenant_data(handler)
    elif path == '/api/scan-voice-files':
        handle_scan_voice_files(handler)
    elif path == '/api/upload-voice':
        handle_upload_voice(handler)
    elif path == '/api/parse-voice-tts':
        handle_parse_voice_tts(handler)
    elif path == '/api/batch-create-voice-tts':
        handle_batch_create_voice_tts(handler)
    elif path == '/api/stop-voice-tts':
        handle_stop_voice_tts(handler)
    elif path == '/api/parse-ticket-templates':
        handle_parse_ticket_templates(handler)
    elif path == '/api/batch-create-ticket-templates':
        handle_batch_create_ticket_templates(handler)
    else:
        send_json(handler, 404, {"success": False, "message": f"Unknown endpoint: {path}"})

def handle_list_ivr_tabs(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
    try:
        req_data = json.loads(body) if body.strip() else {}
        cdp_port = int(req_data.get('cdp_port', 9225))
        cdp_url = req_data.get('cdp_url', '') or None

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser, context, endpoint, was_launched = core.browser.connect_shared_browser(
                p,
                cdp_port=cdp_port,
                cdp_url=cdp_url
            )
            tabs = core.browser.list_active_canvas_tabs(context)
            send_json(handler, 200, {
                "success": True,
                "count": len(tabs),
                "tabs": tabs,
                "endpoint": endpoint
            })
    except Exception as e:
        send_json(handler, 500, {"success": False, "message": str(e), "tabs": [], "count": 0})

def handle_validate_ivr(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        workflow_content = req_data.get('workflow_content', '')
        result = core.ivr.parse_ivr_workflow(workflow_content)
        if result["valid"]:
            send_json(handler, 200, {"success": True, "data": result})
        else:
            send_json(handler, 400, {"success": False, "message": result.get("error", "Validation failed.")})
    except Exception as e:
        send_json(handler, 500, {"success": False, "message": str(e)})

def handle_build_ivr(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        workflow_content = req_data.get('workflow_content', '')
        cdp_port = int(req_data.get('cdp_port', 9225))
        cdp_url = req_data.get('cdp_url', '') or None
        auth_script = req_data.get('auth_script', '')
        tab_mappings = req_data.get('tab_mappings', None)

        auth_data, _ = core.auth.parse_auth_string(auth_script) if auth_script else (None, None)

        handler.send_response(200)
        handler.send_header('Content-Type', 'text/plain; charset=utf-8')
        handler.send_header('Cache-Control', 'no-cache')
        handler.end_headers()

        for chunk in core.ivr.build_ivr_stream(
            workflow_content=workflow_content,
            cdp_port=cdp_port,
            cdp_url=cdp_url,
            auth_data=auth_data,
            tab_mappings=tab_mappings
        ):
            handler.wfile.write(chunk.encode('utf-8'))
            handler.wfile.flush()
    except Exception as e:
        handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8') + b"\n")
        handler.wfile.flush()

def handle_stop_ivr(handler):
    try:
        stopped = core.ivr.request_ivr_stop()
        send_json(handler, 200, {
            "success": True,
            "stopped": stopped,
            "message": "Stop signal sent to active IVR build." if stopped else "No active IVR build found to stop."
        })
    except Exception as e:
        send_json(handler, 500, {"success": False, "message": str(e)})

def handle_fetch_custom_fields(handler, default_owner="Ticket"):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        auth_script = req_data.get('auth_script', '')
        field_owner = req_data.get('field_owner', default_owner)

        auth_data, err = core.auth.parse_auth_string(auth_script)
        if not auth_data:
            send_json(handler, 400, {"success": False, "message": err or "Failed to parse authentication script."})
            return

        success, data, msg = core.fields.fetch_custom_fields(auth_data, field_owner=field_owner)
        send_json(handler, 200 if success else 500, {
            "success": success,
            "count": data.get("count", 0),
            "stats": data.get("stats", {}),
            "fields_json": data.get("fields_json", {}),
            "message": msg
        })
    except Exception as e:
        send_json(handler, 500, {"success": False, "message": str(e)})

def handle_create_custom_fields(handler, default_owner="Ticket"):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        auth_script = req_data.get('auth_script', '')
        fields_list = req_data.get('fields', [])
        field_owner = req_data.get('field_owner', default_owner)

        auth_data, err = core.auth.parse_auth_string(auth_script)
        if not auth_data:
            send_json(handler, 400, {"success": False, "message": err or "Failed to parse authentication script."})
            return

        if not fields_list or not isinstance(fields_list, list):
            send_json(handler, 400, {"success": False, "message": "Fields list must be a non-empty array."})
            return

        roles = req_data.get('roles')

        handler.send_response(200)
        handler.send_header('Content-Type', 'text/plain; charset=utf-8')
        handler.send_header('Cache-Control', 'no-cache')
        handler.end_headers()

        for chunk in core.fields.create_custom_fields_stream(auth_data, fields_list, field_owner=field_owner, all_roles=roles):
            handler.wfile.write(chunk.encode('utf-8'))
            handler.wfile.flush()
    except Exception as e:
        try:
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8') + b"\n")
            handler.wfile.flush()
        except Exception:
            pass

def handle_fetch_customer_fields(handler):
    return handle_fetch_custom_fields(handler, default_owner="Customer")

def handle_create_customer_fields(handler):
    return handle_create_custom_fields(handler, default_owner="Customer")

def handle_parse_custom_fields_file(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        filename = req_data.get('filename', '')
        b64_content = req_data.get('content_base64', '')
        if not b64_content:
            send_json(handler, 400, {"success": False, "message": "Missing file content."})
            return
        file_bytes = base64.b64decode(b64_content)
        success, fields, msg = core.fields.parse_fields_file(file_bytes, filename)
        send_json(handler, 200 if success else 400, {
            "success": success,
            "fields": fields,
            "message": msg
        })
    except Exception as e:
        send_json(handler, 500, {"success": False, "message": str(e)})

def handle_migrate_fields(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        auth_script = req_data.get('auth_script', '')
        raw_data = req_data.get('raw_data', '')

        auth_data, err = core.auth.parse_auth_string(auth_script)
        if not auth_data:
            send_json(handler, 400, {"success": False, "message": err or "Failed to parse authentication script."})
            return

        handler.send_response(200)
        handler.send_header('Content-Type', 'text/plain; charset=utf-8')
        handler.send_header('Cache-Control', 'no-cache')
        handler.end_headers()

        for chunk in core.fields.migrate_fields_stream(raw_data, auth_data):
            handler.wfile.write(chunk.encode('utf-8'))
            handler.wfile.flush()
    except Exception as e:
        try:
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8') + b"\n")
            handler.wfile.flush()
        except Exception:
            pass

def handle_migrate_template(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        auth_a = req_data.get('tenant_a_ps1') or req_data.get('auth_a', '')
        auth_b = req_data.get('tenant_b_ps1') or req_data.get('auth_b', '')
        custom_fields_b = req_data.get('tenant_b_fields') or req_data.get('custom_fields_b', '{}')

        data_a, err_a = core.auth.parse_auth_string(auth_a)
        data_b, err_b = core.auth.parse_auth_string(auth_b)

        if not data_a or not data_b:
            send_json(handler, 400, {"success": False, "message": err_a or err_b or "Failed to parse Tenant A or B authentication scripts."})
            return

        tenant_a_payload = data_a.get("body_json")
        if not tenant_a_payload:
            send_json(handler, 400, {"success": False, "message": "Could not extract JSON payload from Tenant A PowerShell script."})
            return

        if isinstance(custom_fields_b, str):
            try:
                custom_fields_b = json.loads(custom_fields_b)
            except Exception as e:
                send_json(handler, 400, {"success": False, "message": f"Invalid JSON in Tenant B custom fields: {e}"})
                return

        success, msg = core.templates.migrate_template(data_b, tenant_a_payload, custom_fields_b)
        if success:
            send_json(handler, 200, {"success": True, "message": msg})
        else:
            send_json(handler, 500, {"success": False, "message": msg})
    except Exception as e:
        send_json(handler, 500, {"success": False, "message": str(e)})

def handle_create_agent_groups(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        auth_script = req_data.get('auth_script', '')
        group_names = req_data.get('names_list') or req_data.get('group_names', [])

        auth_data, err = core.auth.parse_auth_string(auth_script)
        if not auth_data:
            send_json(handler, 400, {"success": False, "message": err or "Failed to parse authentication script."})
            return

        handler.send_response(200)
        handler.send_header('Content-Type', 'text/plain; charset=utf-8')
        handler.send_header('Cache-Control', 'no-cache')
        handler.end_headers()

        for chunk in core.groups.create_agent_groups_data_stream(auth_data, group_names):
            handler.wfile.write(chunk.encode('utf-8'))
            handler.wfile.flush()
    except Exception as e:
        handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8') + b"\n")
        handler.wfile.flush()

def handle_assign_agents(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        auth_script = req_data.get('auth_script', '')
        groups_json = req_data.get('groups_json', '')
        agents_json = req_data.get('agents_json', '')
        mapping_csv = req_data.get('mapping_csv', '')

        auth_data, err = core.auth.parse_auth_string(auth_script)
        if not auth_data:
            send_json(handler, 400, {"success": False, "message": err or "Failed to parse authentication script."})
            return

        handler.send_response(200)
        handler.send_header('Content-Type', 'text/plain; charset=utf-8')
        handler.send_header('Cache-Control', 'no-cache')
        handler.end_headers()

        for chunk in core.assign.assign_agents_stream(auth_data, groups_json, agents_json, mapping_csv):
            handler.wfile.write(chunk.encode('utf-8'))
            handler.wfile.flush()
    except Exception as e:
        handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8') + b"\n")
        handler.wfile.flush()

def handle_fetch_tenant_data(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        auth_script = req_data.get('auth_script', '')

        auth_data, err = core.auth.parse_auth_string(auth_script)
        if not auth_data:
            send_json(handler, 400, {"success": False, "message": err or "Failed to parse authentication script."})
            return

        success, data, msg = core.assign.fetch_groups_and_agents(auth_data)
        send_json(handler, 200 if success else 500, {
            "success": success,
            "groups_json": data.get("groups_json", {}),
            "agents_json": data.get("agents_json", {}),
            "message": msg
        })
    except Exception as e:
        send_json(handler, 500, {"success": False, "message": str(e)})

def handle_scan_voice_files(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        dir_path = req_data.get('dir_path', '')
        naming_mode = req_data.get('naming_mode', 'folder_suffix')
        prefix = req_data.get('prefix', '')
        suffix = req_data.get('suffix', '')
        pattern = req_data.get('pattern', '')

        success, files_or_err = core.voice.scan_voice_files(
            dir_path=dir_path,
            naming_mode=naming_mode,
            prefix=prefix,
            suffix=suffix,
            pattern=pattern
        )

        if success:
            send_json(handler, 200, {"success": True, "files": files_or_err})
        else:
            send_json(handler, 400, {"success": False, "message": files_or_err})
    except Exception as e:
        send_json(handler, 500, {"success": False, "message": str(e)})

def handle_upload_voice(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        files_to_upload = req_data.get('files', [])
        cdp_port = int(req_data.get('cdp_port', 9225))
        cdp_url = req_data.get('cdp_url', '') or None
        target_url = req_data.get('target_url', '') or None
        auth_script = req_data.get('auth_script', '')
        creds_obj = req_data.get('credentials') if isinstance(req_data.get('credentials'), dict) else {}
        username = req_data.get('username') or creds_obj.get('username', '')
        password = req_data.get('password') or creds_obj.get('password', '')

        auth_data, _ = core.auth.parse_auth_string(auth_script) if auth_script else (None, None)
        custom_creds = {"username": username, "password": password} if (username and password) else None

        handler.send_response(200)
        handler.send_header('Content-Type', 'text/plain; charset=utf-8')
        handler.send_header('Cache-Control', 'no-cache')
        handler.end_headers()

        for chunk in core.voice.upload_voice_stream(
            files_to_upload=files_to_upload,
            cdp_port=cdp_port,
            cdp_url=cdp_url,
            target_url=target_url,
            auth_data=auth_data,
            custom_creds=custom_creds
        ):
            handler.wfile.write(chunk.encode('utf-8'))
            handler.wfile.flush()
    except Exception as e:
        handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8') + b"\n")
        handler.wfile.flush()

def handle_parse_voice_tts(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        text = req_data.get('text', '')
        default_timbre = req_data.get('default_timbre', '小夏')
        success, items, msg = core.voice.parse_voice_tts_text(text, default_timbre=default_timbre)
        send_json(handler, 200 if success else 400, {
            "success": success,
            "items": items,
            "count": len(items),
            "message": msg
        })
    except Exception as e:
        send_json(handler, 500, {"success": False, "message": str(e)})

def handle_batch_create_voice_tts(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        items = req_data.get('items', [])
        cdp_port = int(req_data.get('cdp_port', 9225))
        cdp_url = req_data.get('cdp_url', '') or None
        default_timbre = req_data.get('default_timbre', '小夏')

        if not items:
            send_json(handler, 400, {"success": False, "message": "No voice items provided."})
            return

        handler.send_response(200)
        handler.send_header('Content-Type', 'text/plain; charset=utf-8')
        handler.send_header('Cache-Control', 'no-cache')
        handler.end_headers()

        for chunk in core.voice.create_voice_tts_stream(
            voice_items=items,
            cdp_port=cdp_port,
            cdp_url=cdp_url,
            default_timbre=default_timbre
        ):
            handler.wfile.write(chunk.encode('utf-8'))
            handler.wfile.flush()
    except Exception as e:
        try:
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8') + b"\n")
            handler.wfile.flush()
        except Exception:
            pass

def handle_stop_voice_tts(handler):
    try:
        stopped = core.voice.request_voice_tts_stop()
        send_json(handler, 200, {
            "success": True,
            "stopped": stopped,
            "message": "Stop signal sent to active TTS voice creation." if stopped else "No active TTS voice creation found to stop."
        })
    except Exception as e:
        send_json(handler, 500, {"success": False, "message": str(e)})

def handle_parse_ticket_templates(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        text = req_data.get('text', '')
        auth_script = req_data.get('auth_script', '')
        tenant_fields = req_data.get('tenant_fields')

        success, templates, msg = core.templates.parse_template_blocks(text)
        if not success:
            send_json(handler, 400, {"success": False, "message": msg, "templates": []})
            return

        # Live validation against tenant fields if available
        is_valid = True
        matched_map = {}
        missing_by_template = {}

        if not tenant_fields and auth_script:
            auth_data, err = core.auth.parse_auth_string(auth_script)
            if auth_data:
                f_ok, f_data, _ = core.fields.fetch_custom_fields(auth_data, field_owner="Ticket")
                if f_ok:
                    tenant_fields = f_data.get("fields_json", {})

        duplicate_notices = {}
        if tenant_fields:
            is_valid, matched_map, missing_by_template, duplicate_notices = core.templates.validate_template_fields(templates, tenant_fields)

        total_fields = sum(len(t.get("fields", [])) for t in templates)
        send_json(handler, 200, {
            "success": True,
            "templates": templates,
            "count": len(templates),
            "total_fields": total_fields,
            "is_valid": is_valid,
            "matched_fields": list(matched_map.keys()),
            "missing_by_template": missing_by_template,
            "duplicate_notices": duplicate_notices,
            "message": msg
        })
    except Exception as e:
        send_json(handler, 500, {"success": False, "message": str(e)})

def handle_batch_create_ticket_templates(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        auth_script = req_data.get('auth_script', '')
        templates = req_data.get('templates', [])
        tenant_fields = req_data.get('tenant_fields')

        auth_data, err = core.auth.parse_auth_string(auth_script)
        if not auth_data:
            send_json(handler, 400, {"success": False, "message": err or "Failed to parse authentication script."})
            return

        if not templates:
            send_json(handler, 400, {"success": False, "message": "No ticket templates provided to create."})
            return

        handler.send_response(200)
        handler.send_header('Content-Type', 'text/plain; charset=utf-8')
        handler.send_header('Cache-Control', 'no-cache')
        handler.end_headers()

        for chunk in core.templates.create_ticket_templates_stream(
            auth_data=auth_data,
            templates_list=templates,
            tenant_fields_data=tenant_fields
        ):
            handler.wfile.write(chunk.encode('utf-8'))
            handler.wfile.flush()
    except Exception as e:
        try:
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8') + b"\n")
            handler.wfile.flush()
        except Exception:
            pass

def handle_fetch_agent_metadata(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        auth_script = req_data.get('auth_script', '')
        auth_data, err = core.auth.parse_auth_string(auth_script)
        if not auth_data:
            send_json(handler, 400, {"success": False, "message": err or "Failed to parse authentication script."})
            return
        success, data, msg = core.agents.fetch_agent_metadata(auth_data)
        send_json(handler, 200 if success else 500, {
            "success": success,
            "data": data,
            "message": msg
        })
    except Exception as e:
        send_json(handler, 500, {"success": False, "message": str(e)})

def handle_create_agents(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        auth_script = req_data.get('auth_script', '')
        agents_list = req_data.get('agents', [])
        defaults = req_data.get('defaults', {})

        auth_data, err = core.auth.parse_auth_string(auth_script)
        if not auth_data:
            send_json(handler, 400, {"success": False, "message": err or "Failed to parse authentication script."})
            return

        if not agents_list:
            send_json(handler, 400, {"success": False, "message": "No agent accounts provided to create."})
            return

        handler.send_response(200)
        handler.send_header('Content-Type', 'text/plain; charset=utf-8')
        handler.send_header('Cache-Control', 'no-cache')
        handler.end_headers()

        for chunk in core.agents.create_agents_stream(auth_data, agents_list, defaults=defaults):
            handler.wfile.write(chunk.encode('utf-8'))
            handler.wfile.flush()
    except Exception as e:
        try:
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8') + b"\n")
            handler.wfile.flush()
        except Exception:
            pass

def handle_parse_agents_file(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length).decode('utf-8')
    try:
        req_data = json.loads(body)
        filename = req_data.get('filename', '')
        b64_content = req_data.get('content_base64', '')
        default_profile = req_data.get('default_profile', 'all')
        default_role_ids = req_data.get('default_role_ids')
        if not b64_content:
            send_json(handler, 400, {"success": False, "message": "Missing file content."})
            return
        file_bytes = base64.b64decode(b64_content)
        success, agents, msg = core.agents.parse_agents_file(file_bytes, filename, default_profile=default_profile, default_role_ids=default_role_ids)
        send_json(handler, 200 if success else 400, {
            "success": success,
            "agents": agents,
            "message": msg
        })
    except Exception as e:
        send_json(handler, 500, {"success": False, "message": str(e)})

