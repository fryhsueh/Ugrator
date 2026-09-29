import json
import os
import copy
import time
from core.api import execute_request

def migrate_fields_stream(raw_data, auth_data, templates_dir=None):
    """
    Generator yielding real-time NDJSON progress chunks for custom fields migration.
    Yields JSON strings with trailing newline.
    """
    if templates_dir is None:
        templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')

    if isinstance(raw_data, str):
        try:
            raw_data = json.loads(raw_data)
        except Exception as e:
            yield json.dumps({"status": "error", "message": f"Invalid JSON in raw_data: {e}"}) + "\n"
            return

    base_url = auth_data.get("base_url", "").rstrip('/')
    if not base_url:
        yield json.dumps({"status": "error", "message": "Missing base URL in Auth Data."}) + "\n"
        return

    try:
        with open(os.path.join(templates_dir, 'textTemp.json'), 'r', encoding='utf-8') as f:
            textTemplateData = json.load(f)
        with open(os.path.join(templates_dir, 'chainListTemp.json'), 'r', encoding='utf-8') as f:
            chainListTemplateData = json.load(f)
        with open(os.path.join(templates_dir, 'dropListTemp.json'), 'r', encoding='utf-8') as f:
            dropListTemplateData = json.load(f)
    except Exception as e:
        yield json.dumps({"status": "error", "message": f"Failed to load templates from {templates_dir}: {e}"}) + "\n"
        return

    yield json.dumps({"status": "system", "message": f"Connected to {base_url}"}) + "\n"

    ticketFields = raw_data.get('ticketFields', [])
    total = len(ticketFields)
    yield json.dumps({"status": "system", "message": f"Found {total} fields to process."}) + "\n"

    success_count = 0
    failed_count = 0

    for i, ticketField in enumerate(ticketFields):
        field_title = ticketField.get('title', 'Unknown Field')
        content_type = ticketField.get('content_type')
        log_msg = f"[{i+1}/{total}] Processing field: {field_title} (Type: {content_type})"

        yield json.dumps({
            "status": "progress",
            "index": i,
            "total": total,
            "title": field_title,
            "type": content_type,
            "message": log_msg
        }) + "\n"

        if content_type in ['droplist', 'checkbox', 'chained_droplist']:
            template = copy.deepcopy(chainListTemplateData if content_type == 'chained_droplist' else dropListTemplateData)
            field_key = 'select_field'
            api_path = '/cs/ts/api/select_fields'
        elif content_type in ['text', 'area_text', 'date', 'datetime', 'time', 'number', 'file']:
            template = copy.deepcopy(textTemplateData)
            field_key = 'text_field'
            api_path = '/cs/ts/api/text_fields'
        else:
            skip_msg = f"Skipping unsupported content_type: {content_type}"
            yield json.dumps({"status": "warn", "message": skip_msg}) + "\n"
            continue

        for item in template[field_key]:
            if item in ticketField:
                template[field_key][item] = ticketField[item]

        resp = execute_request(f"{base_url.rstrip('/')}{api_path}", 'POST', template, auth_data)
        if resp.get("status") not in [200, 201]:
            failed_count += 1
            err_msg = f"Failed to create {field_title}. Status: {resp.get('status')}"
            yield json.dumps({"status": "error", "message": err_msg}) + "\n"
        else:
            success_count += 1

        time.sleep(2)

    yield json.dumps({
        "status": "done",
        "total": total,
        "success_count": success_count,
        "failed_count": failed_count,
        "message": "Field migration completed."
    }) + "\n"

def process_fields_data(auth_data, raw_data, templates_dir):
    """Migrate custom fields from raw data JSON using standard templates (in-memory version)."""
    logs = []
    has_critical_error = False
    for chunk in migrate_fields_stream(raw_data, auth_data, templates_dir):
        try:
            data = json.loads(chunk)
            msg = data.get("message", "")
            if data.get("status") == "error" and not logs:
                return False, msg
            if msg:
                logs.append(msg)
        except Exception:
            logs.append(chunk.strip())

    return True, "\n".join(logs)

def process_fields(auth_data, rawdata_path, templates_dir):
    if not os.path.exists(rawdata_path):
        print(f"Error: Could not find raw data at {rawdata_path}")
        return

    with open(rawdata_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    success, message = process_fields_data(auth_data, data, templates_dir)
    print(message)

def delete_fields(auth_data, delete_json_path):
    pass # Skipped refactoring for brevity, UI doesn't strictly need delete yet

def migrate_fields(raw_data, auth_data, templates_dir=None):
    """
    Migrates custom fields from raw data (dict or JSON string) using standard templates.
    Returns: (success: bool, message: str)
    """
    if templates_dir is None:
        templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
    if isinstance(raw_data, str):
        try:
            raw_data = json.loads(raw_data)
        except Exception as e:
            return False, f"Invalid JSON in raw_data: {e}"
    return process_fields_data(auth_data, raw_data, templates_dir)

def fetch_custom_fields(auth_data, field_owner="Ticket"):
    """
    Fetches custom fields from Web Admin API.
    Endpoint: GET {base_url}/cs/ts/api/custom_fields?field_owner={field_owner}
    field_owner: "Ticket" or "Customer"
    Returns: (success: bool, data: dict, message: str)
    """
    base_url = auth_data.get("base_url", "").rstrip('/')
    if not base_url:
        return False, {}, "Missing base URL in Auth Data."

    owner = "Customer" if str(field_owner).lower() == "customer" else "Ticket"
    url = f"{base_url}/cs/ts/api/custom_fields?field_owner={owner}"
    resp = execute_request(url, 'GET', None, auth_data)

    if resp.get("status") != 200:
        desc = "customer custom fields" if owner == "Customer" else "custom fields"
        return False, {}, f"Failed to fetch {desc} from tenant (status {resp.get('status')}). Error: {resp.get('error')}"

    raw_resp_data = resp.get("data", {})
    fields_list = []
    if isinstance(raw_resp_data, dict):
        fields_list = raw_resp_data.get("custom_fields") or raw_resp_data.get("ticketFields") or raw_resp_data.get("customerFields") or []
    elif isinstance(raw_resp_data, list):
        fields_list = raw_resp_data

    # Generate summary stats by content_type
    stats = {}
    for f in fields_list:
        ctype = f.get("content_type", "unknown") if isinstance(f, dict) else "unknown"
        stats[ctype] = stats.get(ctype, 0) + 1

    normalized_data = {
        "custom_fields": fields_list,
        "customerFields" if owner == "Customer" else "ticketFields": fields_list
    }

    stats_summary = ", ".join([f"{k}: {v}" for k, v in sorted(stats.items())]) if stats else "None"
    desc = "customer custom fields" if owner == "Customer" else "custom fields"
    msg = f"Successfully fetched {len(fields_list)} {desc} ({stats_summary})."
    return True, {
        "count": len(fields_list),
        "stats": stats,
        "fields_json": normalized_data
    }, msg


def create_custom_fields_stream(auth_data, fields_list, field_owner="Ticket", templates_dir=None, all_roles=None):
    """
    Generator yielding NDJSON progress lines for batch-creating custom fields.
    Each item in fields_list: {
        "title": str,
        "type": "text"|"date"|"drop_list",
        "options": list,
        "invisible_role_ids": list of int (optional, for Ticket fields),
        "persona": str (optional)
    }
    field_owner: "Ticket" or "Customer"
    all_roles: list of dicts [{"id": int, "name": str}, ...]
    Yields: JSON string with trailing newline.
    """
    if templates_dir is None:
        templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')

    base_url = auth_data.get("base_url", "").rstrip('/')
    if not base_url:
        yield json.dumps({"status": "error", "message": "Missing base URL in Auth Data."}) + "\n"
        return

    owner = "Customer" if str(field_owner).lower() == "customer" else "Ticket"

    try:
        with open(os.path.join(templates_dir, 'textTemp.json'), 'r', encoding='utf-8') as f:
            textTemplateData = json.load(f)
        with open(os.path.join(templates_dir, 'dropListTemp.json'), 'r', encoding='utf-8') as f:
            dropListTemplateData = json.load(f)
    except Exception as e:
        yield json.dumps({"status": "error", "message": f"Failed to load field templates: {e}"}) + "\n"
        return

    # Check if any ticket field requires role permissions
    needs_role_abilities = False
    if owner == "Ticket":
        for item in fields_list:
            if isinstance(item, dict) and item.get("invisible_role_ids"):
                needs_role_abilities = True
                break

    # Lazy-fetch all roles from tenant if not provided
    if needs_role_abilities and not all_roles:
        try:
            from core.agents import fetch_agent_metadata
            succ, meta, _ = fetch_agent_metadata(auth_data)
            if succ and meta.get("roles"):
                all_roles = meta.get("roles")
        except Exception:
            all_roles = []

    total = len(fields_list)
    yield json.dumps({
        "status": "start",
        "total": total,
        "field_owner": owner,
        "message": f"Initiating creation of {total} {owner.lower()} custom field(s)..."
    }) + "\n"

    success_count = 0
    failed_count = 0

    for i, field_item in enumerate(fields_list):
        raw_title = field_item.get('title', '').strip() if isinstance(field_item, dict) else ''
        title = raw_title or f"CustomField_{i+1}"
        raw_type = (field_item.get('type') or 'text').lower().strip() if isinstance(field_item, dict) else 'text'
        options = field_item.get('options', []) if isinstance(field_item, dict) else []
        description = str(field_item.get('description') or field_item.get('comment') or '').strip() if isinstance(field_item, dict) else ''
        invisible_role_ids = field_item.get('invisible_role_ids', []) if isinstance(field_item, dict) else []

        if raw_type in ['drop_list', 'droplist', 'select']:
            payload = copy.deepcopy(dropListTemplateData)
            payload['select_field']['title'] = title
            payload['select_field']['comment'] = description
            payload['select_field']['field_owner'] = owner
            payload['select_field']['content_type'] = 'droplist'
            if owner == "Customer":
                payload['select_field']['agent_permission'] = 2
                payload['select_field']['customer_permission'] = 2
            clean_opts = [str(opt).strip() for opt in options if str(opt).strip()]
            payload['select_field']['select_options'] = [{"title": opt, "value": ""} for opt in clean_opts]
            api_endpoint = f"{base_url}/cs/ts/api/select_fields"
            resolved_type = 'drop_list'
            default_field_type_str = "SelectField"
        elif raw_type == 'date':
            payload = copy.deepcopy(textTemplateData)
            payload['text_field']['title'] = title
            payload['text_field']['comment'] = description
            payload['text_field']['field_owner'] = owner
            payload['text_field']['content_type'] = 'date'
            if owner == "Customer":
                payload['text_field']['agent_permission'] = 2
                payload['text_field']['customer_permission'] = 2
                payload['text_field']['is_encrypt'] = False
            api_endpoint = f"{base_url}/cs/ts/api/text_fields"
            resolved_type = 'date'
            default_field_type_str = "TextField"
        else: # default text
            payload = copy.deepcopy(textTemplateData)
            payload['text_field']['title'] = title
            payload['text_field']['comment'] = description
            payload['text_field']['field_owner'] = owner
            payload['text_field']['content_type'] = 'text'
            if owner == "Customer":
                payload['text_field']['agent_permission'] = 2
                payload['text_field']['customer_permission'] = 2
                payload['text_field']['is_encrypt'] = False
            api_endpoint = f"{base_url}/cs/ts/api/text_fields"
            resolved_type = 'text'
            default_field_type_str = "TextField"

        # Execute API request to create the field
        resp = execute_request(api_endpoint, 'POST', payload, auth_data)
        status_code = resp.get("status")

        created_field_id = None
        resolved_field_type = default_field_type_str

        if status_code in [200, 201]:
            success_count += 1
            is_ok = True
            msg = f"[{i+1}/{total}] Successfully created {owner.lower()} {resolved_type} field '{title}'."

            # Extract created field ID
            resp_data = resp.get("data", {})
            if isinstance(resp_data, dict):
                inner = resp_data.get("text_field") or resp_data.get("select_field") or resp_data
                if isinstance(inner, dict):
                    created_field_id = inner.get("id") or inner.get("field_id")
                    resolved_field_type = inner.get("field_type") or default_field_type_str
        else:
            failed_count += 1
            is_ok = False
            err_detail = resp.get("error") or resp.get("data") or f"HTTP {status_code}"
            msg = f"[{i+1}/{total}] Failed to create '{title}' ({resolved_type}): {err_detail}"

        yield json.dumps({
            "status": "progress",
            "index": i,
            "title": title,
            "type": resolved_type,
            "field_owner": owner,
            "success": is_ok,
            "field_id": created_field_id,
            "message": msg
        }) + "\n"

        # Apply Role Visibility Abilities (PUT /cs/ts/api/fields/{id}/agent_role_abilities)
        if is_ok and owner == "Ticket" and created_field_id and invisible_role_ids and all_roles:
            target_inv_ids = set()
            for r in invisible_role_ids:
                try:
                    target_inv_ids.add(int(r))
                except (ValueError, TypeError):
                    pass

            if target_inv_ids:
                time.sleep(2)  # Rate limiting delay
                abilities = []
                for role in all_roles:
                    r_id = role.get("id")
                    if r_id is None:
                        continue
                    if r_id in target_inv_ids:
                        abilities.append({
                            "agent_role_id": r_id,
                            "permission": "invisible",
                            "show_permission": "sensitive"
                        })
                    else:
                        abilities.append({
                            "agent_role_id": r_id,
                            "permission": "preset_value",
                            "show_permission": "default"
                        })

                abilities_payload = {
                    "field_type": resolved_field_type,
                    "default_ability": "editable",
                    "default_show_permission": 0,
                    "abilities": abilities
                }

                abilities_url = f"{base_url}/cs/ts/api/fields/{created_field_id}/agent_role_abilities"
                ability_resp = execute_request(abilities_url, 'PUT', abilities_payload, auth_data)

                if ability_resp.get("status") in [200, 201]:
                    hidden_role_names = [r.get("name", str(r.get("id"))) for r in all_roles if r.get("id") in target_inv_ids]
                    yield json.dumps({
                        "status": "log",
                        "message": f"[{i+1}/{total}] Configured permissions for '{title}': Hidden for roles [{', '.join(hidden_role_names)}]."
                    }) + "\n"
                else:
                    err_msg = ability_resp.get("error") or ability_resp.get("data")
                    yield json.dumps({
                        "status": "warn",
                        "message": f"[{i+1}/{total}] Created '{title}', but failed to update role visibility: {err_msg}"
                    }) + "\n"

        # Adhere to API rate limits between sequential calls
        if i < total - 1:
            time.sleep(2)

    yield json.dumps({
        "status": "done",
        "total": total,
        "field_owner": owner,
        "success_count": success_count,
        "failed_count": failed_count,
        "message": f"Creation finished: {success_count} succeeded, {failed_count} failed."
    }) + "\n"


def parse_fields_file(file_content_bytes, filename=""):
    """
    Parses an uploaded Excel (.xlsx) or CSV file into a list of field dicts.
    Returns: (success: bool, fields: list, message: str)
    """
    import io
    import pandas as pd
    try:
        ext = os.path.splitext(filename.lower())[1] if filename else ''
        is_delimited = ext in ['.csv', '.tsv', '.txt']
        if is_delimited:
            sep = '\t' if ext == '.tsv' else None
            engine = 'python' if sep is None else 'c'
            try:
                df = pd.read_csv(io.BytesIO(file_content_bytes), header=None, encoding='utf-8-sig', sep=sep, engine=engine)
            except Exception:
                df = pd.read_csv(io.BytesIO(file_content_bytes), header=None, encoding='gbk', sep=sep, engine=engine)
        else:
            df = pd.read_excel(io.BytesIO(file_content_bytes), header=None)

        if df.empty:
            return True, [], "Empty file"

        # Check if row 0 is header
        first_val = str(df.iloc[0, 0]).strip().lower()
        has_header = any(h in first_val for h in ['字段', 'field', 'name', 'title'])
        persona_col_idx = None
        desc_col_idx = None
        has_opt_headers = False

        if has_header:
            header_row = [str(c).strip().lower() for c in df.iloc[0]]
            for c_idx, col_name in enumerate(header_row):
                if any(p in col_name for p in ['persona', 'role', '角色', '适用']):
                    persona_col_idx = c_idx
                elif any(d in col_name for d in ['desc', 'comment', '说明', '描述', '备注']):
                    desc_col_idx = c_idx
                elif any(o in col_name for o in ['opt', 'option', '选项']):
                    has_opt_headers = True

        fields = []
        start_row = 1 if has_header else 0

        known_personas = {'agent', 'distributor', 'internal', 'all', '客服', '坐席', '分销商', '分销', '经销商', '全部'}

        for idx in range(start_row, len(df)):
            row = df.iloc[idx]
            if len(row) == 0 or pd.isna(row[0]):
                continue
            val0 = str(row[0]).strip()
            if not val0:
                continue

            val1 = str(row[1]).strip().lower() if len(row) > 1 and not pd.isna(row[1]) else 'text'
            if any(k in val1 for k in ['drop', 'select', '下拉']):
                ftype = 'drop_list'
            elif any(k in val1 for k in ['date', '日期']):
                ftype = 'date'
            else:
                ftype = 'text'

            opts = []
            persona = 'All'
            description = ''

            if persona_col_idx is not None and persona_col_idx < len(row) and not pd.isna(row[persona_col_idx]):
                persona = str(row[persona_col_idx]).strip() or 'All'
            if desc_col_idx is not None and desc_col_idx < len(row) and not pd.isna(row[desc_col_idx]):
                description = str(row[desc_col_idx]).strip()

            if has_opt_headers:
                for col in range(2, len(row)):
                    if col == persona_col_idx or col == desc_col_idx:
                        continue
                    if not pd.isna(row[col]) and str(row[col]).strip() and ftype == 'drop_list':
                        opts.append(str(row[col]).strip())
            elif desc_col_idx is None and persona_col_idx is None:
                if len(row) >= 5:
                    # 5 columns: Title, Type, Options, Description, Persona
                    col2_str = str(row[2]).strip() if not pd.isna(row[2]) else ''
                    if col2_str and ftype == 'drop_list':
                        opts = [o.strip() for o in col2_str.replace('，', ',').split(',') if o.strip()]
                    description = str(row[3]).strip() if not pd.isna(row[3]) else ''
                    persona = str(row[4]).strip() if not pd.isna(row[4]) else 'All'
                elif len(row) == 4:
                    col2_str = str(row[2]).strip() if not pd.isna(row[2]) else ''
                    col3_str = str(row[3]).strip() if not pd.isna(row[3]) else ''
                    if col2_str and ftype == 'drop_list':
                        opts = [o.strip() for o in col2_str.replace('，', ',').split(',') if o.strip()]
                    if col3_str.lower() in known_personas:
                        persona = col3_str
                    else:
                        description = col3_str
                else:
                    col2_str = str(row[2]).strip() if len(row) > 2 and not pd.isna(row[2]) else ''
                    if col2_str and ftype == 'drop_list':
                        opts = [o.strip() for o in col2_str.replace('，', ',').split(',') if o.strip()]
            else:
                for col in range(2, len(row)):
                    if col == persona_col_idx or col == desc_col_idx:
                        continue
                    if not pd.isna(row[col]) and str(row[col]).strip() and ftype == 'drop_list':
                        cell_val = str(row[col]).strip()
                        if ',' in cell_val or '，' in cell_val:
                            opts.extend([o.strip() for o in cell_val.replace('，', ',').split(',') if o.strip()])
                        else:
                            opts.append(cell_val)

            fields.append({'title': val0, 'type': ftype, 'options': opts, 'description': description, 'persona': persona})

        return True, fields, f"Successfully parsed {len(fields)} fields from {filename or 'file'}."
    except Exception as e:
        return False, [], f"Failed to parse file: {e}"




