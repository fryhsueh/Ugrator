import json
import copy
import os
import re
import time
from core.api import execute_request

def migrate_template_data(tenant_b_auth, tenant_a_payload, tenant_b_fields_data):
    """
    1. Extracts target Template ID from Tenant B Auth.
    2. Maps the fields from Tenant A -> Tenant B.
    3. PUTs the mapped configuration to the Template.
    """
    base_url = tenant_b_auth["base_url"]
    logs = []
    
    # Deep-copy to prevent destructive in-place mutation of the caller's data
    tenant_a_payload = copy.deepcopy(tenant_a_payload)
    
    target_template_id = tenant_b_auth.get("template_id")
    if not target_template_id:
        return False, "Error: Could not find the target Template ID in the Tenant B PowerShell script. Are you sure you copied the request from saving an existing template?"
        
    logs.append(f"Step 1: Identified target Template ID: {target_template_id}")
    
    # Step 2: Map Fields
    logs.append("Step 2: Mapping field IDs from Tenant A to Tenant B...")
    tenant_b_fields = tenant_b_fields_data.get('ticketFields', [])
    tenant_b_map = {f.get('title'): f for f in tenant_b_fields if f.get('title')}
    
    tenant_a_fields = tenant_a_payload.get('ticket_template', {}).get('fields', [])
    if not tenant_a_fields:
        return False, "\n".join(logs) + "\nError: Could not find any fields in the Tenant A payload. Are you sure the script contained the JSON Body?"
        
    mapped_fields = []
    missing_fields = []
    
    for a_field in tenant_a_fields:
        title = a_field.get('title')
        if title in tenant_b_map:
            b_field = tenant_b_map[title]
            
            # Map the IDs to Tenant B
            a_field['id'] = b_field['id']
            a_field['field_id'] = b_field['field_id']
            a_field['name'] = b_field['name']
            
            mapped_fields.append(a_field)
        else:
            missing_fields.append(title)
            
    if missing_fields:
        logs.append(f"WARNING: {len(missing_fields)} fields were NOT found in Tenant B and will be skipped.")
            
    tenant_a_payload['ticket_template']['fields'] = mapped_fields
    tenant_a_payload['ticket_template']['id'] = target_template_id
    
    # Step 3: Update the template
    logs.append(f"Step 3: Applying mapped configuration to Template {target_template_id}...")
    update_url = f"{base_url.rstrip('/')}/cs/ts/api/ticket_templates/{target_template_id}"
    update_resp = execute_request(update_url, 'PUT', tenant_a_payload, tenant_b_auth)
    
    if update_resp.get("status") == 200:
        logs.append("Successfully applied the configuration!")
        return True, "\n".join(logs)
    else:
        logs.append(f"Failed to apply configuration. Status: {update_resp.get('status')}")
        logs.append(f"Response: {update_resp.get('error')}")
        return False, "\n".join(logs)

def migrate_template(tenant_b_auth, tenant_a_payload, tenant_b_fields_data):
    success, message = migrate_template_data(tenant_b_auth, tenant_a_payload, tenant_b_fields_data)
    print(message)
    return success, message

def parse_template_blocks(text):
    """
    Parses hierarchical template blocks from text or TSV into structured template definitions.
    
    Supported formats:
        Template: Complaint Ticket
        VIN	true
        Car Model	false
        Dealer Code*
        
        模板：保养工单
        车牌号	必填
        行驶里程	选填
    """
    if not text or not text.strip():
        return False, [], "No template definitions provided."

    templates = []
    current_template = None
    lines = text.strip().splitlines()

    header_patterns = [
        re.compile(r'^(?:template|ticket\s*template|工单模板|模板)\s*[:：]\s*(.+)$', re.IGNORECASE),
        re.compile(r'^\[(.+)\]$'),
        re.compile(r'^#{1,4}\s+(.+)$')
    ]

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        # Check if line is a template header (headers do not contain tabs and cannot be pure #ID)
        is_header = False
        template_name = ""
        if '\t' not in line and not re.match(r'^#\d+', line):
            for pat in header_patterns:
                m = pat.match(line)
                if m:
                    is_header = True
                    template_name = m.group(1).strip()
                    break

        if is_header and template_name:
            current_template = {
                "name": template_name,
                "fields": []
            }
            templates.append(current_template)
            continue

        # If not a header, it's a field line
        if current_template is None:
            # Default template for leading field rows
            current_template = {
                "name": "Default Template",
                "fields": []
            }
            templates.append(current_template)

        # Strip markdown bullets: "- ", "* ", "1. ", "• "
        field_line = re.sub(r'^(?:[-*•]|\d+\.)\s+', '', line).strip()
        if not field_line:
            continue

        # Determine delimiter: tab preferred, fallback to comma
        if '\t' in field_line:
            parts = [p.strip() for p in field_line.split('\t')]
        elif ',' in field_line:
            parts = [p.strip() for p in field_line.split(',')]
        else:
            parts = [field_line]

        raw_title = parts[0]
        col_req = parts[1].lower() if len(parts) > 1 else ""

        is_required = False
        # Check explicit column requirement
        if col_req in ['true', '1', 'yes', 'required', '必填', 'y']:
            is_required = True
        elif col_req in ['false', '0', 'no', 'optional', '选填', 'n']:
            is_required = False
        else:
            # Check inline markers in title: e.g. *Title, Title*, Title (required), Title(必填)
            if '*' in raw_title:
                is_required = True
                raw_title = raw_title.replace('*', '').strip()
            inline_req = re.search(r'[\(（]\s*(required|必填)\s*[\)）]', raw_title, re.IGNORECASE)
            inline_opt = re.search(r'[\(（]\s*(optional|选填)\s*[\)）]', raw_title, re.IGNORECASE)
            if inline_req:
                is_required = True
                raw_title = re.sub(r'[\(（]\s*(required|必填)\s*[\)）]', '', raw_title, flags=re.IGNORECASE).strip()
            elif inline_opt:
                is_required = False
                raw_title = re.sub(r'[\(（]\s*(optional|选填)\s*[\)）]', '', raw_title, flags=re.IGNORECASE).strip()

        # Check if raw_title specifies an explicit ID or field code
        target_id = None
        target_name = None

        # 1. Pure ID: "#12345" or "12345"
        m_pure_id = re.match(r'^#?(\d+)$', raw_title)
        if m_pure_id:
            target_id = m_pure_id.group(1)
            target_name = f"field_{target_id}"

        # 2. Pure Field Code: "field_12345"
        elif re.match(r'^field_(\d+)$', raw_title, re.IGNORECASE):
            m_code = re.match(r'^field_(\d+)$', raw_title, re.IGNORECASE)
            target_id = m_code.group(1)
            target_name = raw_title.lower()

        # 3. Non-numeric field code: e.g. "field_custom_code"
        elif re.match(r'^field_[a-zA-Z0-9_]+$', raw_title, re.IGNORECASE):
            target_name = raw_title.lower()

        # 4. Title with embedded ID: "VIN (#12345)", "VIN (ID: 12345)", "VIN [12345]", "VIN #12345", "VIN (field_12345)"
        else:
            m_embedded = re.search(r'^(.*?)\s*[\(\[]\s*(?:id\s*[:：]?\s*|#)?(?:field_)?(\d+)\s*[\)\]]$', raw_title, re.IGNORECASE)
            if not m_embedded:
                m_embedded = re.search(r'^(.*?)\s+#(\d+)$', raw_title)
            
            if m_embedded:
                extracted_title = m_embedded.group(1).strip()
                extracted_id = m_embedded.group(2).strip()
                if extracted_id:
                    target_id = extracted_id
                    target_name = f"field_{target_id}"
                if extracted_title:
                    raw_title = extracted_title

        if raw_title or target_id or target_name:
            field_entry = {
                "title": raw_title or (f"#{target_id}" if target_id else target_name),
                "required": is_required
            }
            if target_id:
                field_entry["target_id"] = str(target_id)
            if target_name:
                field_entry["target_name"] = str(target_name)

            current_template["fields"].append(field_entry)

    # Filter out empty templates
    valid_templates = [t for t in templates if t["fields"] or t["name"]]
    if not valid_templates:
        return False, [], "No valid templates or fields extracted from text."

    total_fields = sum(len(t["fields"]) for t in valid_templates)
    return True, valid_templates, f"Successfully parsed {len(valid_templates)} template(s) with {total_fields} field(s)."

def validate_template_fields(templates_list, tenant_fields_data):
    """
    Validates template fields against the tenant's ticket fields.
    Supports matching by:
    - Target ID / field_id (e.g. 28101, #28101)
    - Target name (e.g. field_28101, priority)
    - Title / display name (e.g. VIN, Car Model)
    Returns:
        is_valid (bool): True if all fields exist in tenant, False otherwise.
        matched_map (dict): lookup key -> tenant field dict
        missing_by_template (dict): template_name -> list of missing identifiers
        duplicate_notices (dict): title -> list of matching IDs (for disambiguation)
    """
    tenant_fields = []
    if isinstance(tenant_fields_data, dict):
        tenant_fields = (tenant_fields_data.get('ticketFields') or 
                         tenant_fields_data.get('custom_fields') or 
                         tenant_fields_data.get('data', {}).get('ticketFields') or [])
    elif isinstance(tenant_fields_data, list):
        tenant_fields = tenant_fields_data

    id_map = {}
    field_id_map = {}
    name_map = {}
    title_map = {} # title -> list of fields (to handle duplicates)

    for f in tenant_fields:
        if isinstance(f, dict):
            f_id = f.get('id')
            if f_id is not None:
                id_map[str(f_id)] = f

            f_custom_id = f.get('field_id')
            if f_custom_id is not None:
                field_id_map[str(f_custom_id)] = f

            f_name = f.get('name')
            if f_name:
                name_map[str(f_name).lower()] = f

            title = str(f.get('title', '')).strip()
            if title:
                title_map.setdefault(title, []).append(f)
                title_map.setdefault(title.lower(), []).append(f)

    matched_map = {}
    missing_by_template = {}
    duplicate_notices = {}
    total_missing = 0

    for tpl in templates_list:
        tpl_name = tpl.get("name", "Unknown")
        missing_fields = []
        for field in tpl.get("fields", []):
            f_title = field.get("title", "").strip()
            target_id = str(field.get("target_id", "")).strip()
            target_name = str(field.get("target_name", "")).strip().lower()

            found_field = None

            # 1. Match by explicit target_id (id or field_id)
            if target_id:
                found_field = id_map.get(target_id) or field_id_map.get(target_id)

            # 2. Match by explicit target_name
            if not found_field and target_name:
                found_field = name_map.get(target_name)

            # 3. Match if f_title is purely numeric or starts with #
            if not found_field:
                clean_num = f_title.lstrip('#').strip()
                if clean_num.isdigit():
                    found_field = id_map.get(clean_num) or field_id_map.get(clean_num)

            # 4. Match if f_title starts with field_
            if not found_field and f_title.lower().startswith('field_'):
                found_field = name_map.get(f_title.lower())

            # 5. Match by title
            if not found_field and f_title:
                matches = title_map.get(f_title) or title_map.get(f_title.lower()) or []
                unique_matches = []
                seen_ids = set()
                for m in matches:
                    mid = m.get('id')
                    if mid not in seen_ids:
                        seen_ids.add(mid)
                        unique_matches.append(m)

                if len(unique_matches) == 1:
                    found_field = unique_matches[0]
                elif len(unique_matches) > 1:
                    # Duplicate titles in tenant! Pick first, record duplicate warning
                    found_field = unique_matches[0]
                    dup_ids = [str(m.get('id')) for m in unique_matches if m.get('id')]
                    duplicate_notices[f_title] = dup_ids
                    field["has_duplicates"] = True
                    field["duplicate_ids"] = dup_ids

            if found_field:
                matched_map[f_title] = found_field
                if target_id:
                    matched_map[target_id] = found_field
                if target_name:
                    matched_map[target_name] = found_field
                if found_field.get("id"):
                    matched_map[str(found_field["id"])] = found_field
                if found_field.get("name"):
                    matched_map[str(found_field["name"]).lower()] = found_field

                # Annotate field item with resolved display details
                field["display_title"] = found_field.get("title") or f_title
                field["resolved_id"] = found_field.get("id")
                field["resolved_name"] = found_field.get("name")
            else:
                display_missing = f_title or (f"#{target_id}" if target_id else target_name)
                missing_fields.append(display_missing)
                total_missing += 1

        if missing_fields:
            missing_by_template[tpl_name] = missing_fields

    is_valid = (total_missing == 0)
    return is_valid, matched_map, missing_by_template, duplicate_notices

def create_ticket_templates_stream(auth_data, templates_list, tenant_fields_data=None):
    """
    Generator yielding NDJSON streaming events for creating ticket templates.
    Honors Strict Guard validation and 2-second rate-limiting.
    """
    import time
    from core.fields import fetch_custom_fields

    base_url = auth_data.get("base_url", "").rstrip('/')
    if not base_url:
        yield json.dumps({"status": "error", "message": "Missing base URL in Auth Data."}) + "\n"
        return

    total_templates = len(templates_list)
    if total_templates == 0:
        yield json.dumps({"status": "error", "message": "No templates provided to create."}) + "\n"
        return

    yield json.dumps({"status": "info", "message": f"Validating {total_templates} template(s) against tenant ticket fields..."}) + "\n"

    # Fetch tenant ticket fields if not provided
    if not tenant_fields_data:
        yield json.dumps({"status": "info", "message": "Fetching live ticket fields from tenant..."}) + "\n"
        success, data, msg = fetch_custom_fields(auth_data, field_owner="Ticket")
        if not success:
            yield json.dumps({"status": "error", "message": f"Failed to fetch tenant fields: {msg}"}) + "\n"
            return
        tenant_fields_data = data.get("fields_json", {})

    # Strict Guard Validation
    is_valid, matched_map, missing_by_template, duplicate_notices = validate_template_fields(templates_list, tenant_fields_data)
    if not is_valid:
        error_details = []
        for tpl_name, missing in missing_by_template.items():
            error_details.append(f"• [{tpl_name}]: Missing {len(missing)} field(s): {', '.join(missing)}")
        err_msg = "Strict Guard Failed: Cannot create templates because some referenced fields do not exist in tenant:\n" + "\n".join(error_details) + "\n\n👉 Please create these custom fields first in the 'Create Custom Fields' tab."
        yield json.dumps({
            "status": "error",
            "message": err_msg,
            "data": {
                "missing_by_template": missing_by_template
            }
        }) + "\n"
        return

    if duplicate_notices:
        dup_msgs = []
        for d_title, d_ids in duplicate_notices.items():
            dup_msgs.append(f"Field '{d_title}' matches multiple tenant fields with identical title (IDs: {', '.join(d_ids)}). Matched ID #{d_ids[0]}. To select a different one, specify '{d_title} (#{d_ids[-1]})'.")
        yield json.dumps({
            "status": "info",
            "message": "Duplicate Notice:\n" + "\n".join(dup_msgs)
        }) + "\n"

    yield json.dumps({"status": "info", "message": f"Validation passed! All referenced fields exist in tenant. Beginning creation of {total_templates} template(s)..."}) + "\n"

    success_count = 0
    failed_count = 0

    for idx, tpl in enumerate(templates_list, 1):
        tpl_name = tpl.get("name", f"Template_{idx}")
        raw_fields = tpl.get("fields", [])
        
        # Build mapped fields array
        mapped_fields = []
        for f in raw_fields:
            title = f.get("title", "").strip()
            target_id = str(f.get("target_id", "")).strip()
            target_name = str(f.get("target_name", "")).strip().lower()
            resolved_id = str(f.get("resolved_id", "")).strip()

            field_info = (
                (matched_map.get(resolved_id) if resolved_id else None) or
                (matched_map.get(target_id) if target_id else None) or
                (matched_map.get(target_name) if target_name else None) or
                matched_map.get(title) or
                matched_map.get(title.lower())
            )
            if field_info:
                f_id = field_info.get("field_id") or field_info.get("id")
                f_type = field_info.get("field_type")
                if not f_type:
                    ctype = str(field_info.get("content_type", "")).lower()
                    if "drop" in ctype or "select" in ctype:
                        f_type = "DropListField"
                    elif "numeric" in ctype or "number" in ctype:
                        f_type = "NumericField"
                    elif "date" in ctype:
                        f_type = "DateField"
                    else:
                        f_type = "TextField"

                f_name = field_info.get("name") or f"{f_type}_{f_id}"
                is_req = bool(f.get("required", False))

                field_entry = {
                    "id": f_name,
                    "name": f_name,
                    "field_id": int(f_id) if str(f_id).isdigit() else f_id,
                    "field_type": f_type,
                    "content_type": field_info.get("content_type", "text"),
                    "title": field_info.get("title", title),
                    "comment": field_info.get("comment", ""),
                    "is_required": is_req,
                    "required": is_req
                }
                mapped_fields.append(field_entry)

        payload = {
            "ticket_template": {
                "name": tpl_name,
                "description": tpl.get("description", ""),
                "use_scope_type": "all_agents",
                "use_scope_content": [],
                "email_support_api": True,
                "default": False,
                "template_rule_enable": False,
                "fields": mapped_fields
            }
        }

        yield json.dumps({
            "status": "progress",
            "message": f"[{idx}/{total_templates}] Creating template '{tpl_name}' with {len(mapped_fields)} field(s)...",
            "data": {"index": idx, "name": tpl_name, "fields_count": len(mapped_fields)}
        }) + "\n"

        create_url = f"{base_url}/cs/ts/api/ticket_templates"
        create_resp = execute_request(create_url, 'POST', payload, auth_data)

        if create_resp.get("status") in [200, 201]:
            resp_data = create_resp.get("data", {})
            if isinstance(resp_data, dict) and resp_data.get("code") not in [None, 1000, 200, 201]:
                failed_count += 1
                err_detail = resp_data.get("message") or resp_data.get("error") or str(resp_data)
                yield json.dumps({
                    "status": "error",
                    "message": f"[{idx}/{total_templates}] Failed to create template '{tpl_name}': {err_detail}",
                    "data": {"index": idx, "name": tpl_name, "status": "failed", "error": err_detail}
                }) + "\n"
            else:
                template_obj = resp_data.get("data") if isinstance(resp_data.get("data"), dict) else (resp_data.get("ticket_template") or resp_data)
                created_id = template_obj.get("id") or template_obj.get("ticket_template_id", "N/A")
                created_fields_count = len(template_obj.get("fields", [])) if isinstance(template_obj.get("fields"), list) else len(mapped_fields)
                success_count += 1
                yield json.dumps({
                    "status": "info",
                    "message": f"[{idx}/{total_templates}] Successfully created template '{tpl_name}' (ID: {created_id}) with {created_fields_count} field(s).",
                    "data": {"index": idx, "name": tpl_name, "id": created_id, "status": "success"}
                }) + "\n"
        else:
            failed_count += 1
            err_detail = create_resp.get("error") or f"HTTP {create_resp.get('status')}"
            yield json.dumps({
                "status": "error",
                "message": f"[{idx}/{total_templates}] Failed to create template '{tpl_name}': {err_detail}",
                "data": {"index": idx, "name": tpl_name, "status": "failed", "error": err_detail}
            }) + "\n"

        # Rate limiting: 2-second sleep between sequential templates
        if idx < total_templates:
            time.sleep(2)

    summary_msg = f"Ticket template creation completed. Total: {total_templates} | Succeeded: {success_count} | Failed: {failed_count}"
    yield json.dumps({
        "status": "done",
        "message": summary_msg,
        "data": {"total": total_templates, "success": success_count, "failed": failed_count}
    }) + "\n"

def fetch_live_templates(auth_data):
    """
    Fetches all ticket templates currently configured in the tenant.
    Returns: (success: bool, templates_list: list, message: str)
    """
    base_url = auth_data.get("base_url", "").rstrip('/')
    if not base_url:
        return False, [], "Missing base URL in Auth Data."

    url = f"{base_url}/cs/ts/api/ticket_templates"
    resp = execute_request(url, 'GET', {}, auth_data)

    if resp.get("status") != 200:
        err = resp.get("error") or f"HTTP {resp.get('status')}"
        return False, [], f"Failed to fetch ticket templates: {err}"

    resp_data = resp.get("data", {})
    templates = []
    if isinstance(resp_data, list):
        templates = resp_data
    elif isinstance(resp_data, dict):
        templates = (
            resp_data.get("items") or
            resp_data.get("ticket_templates") or
            resp_data.get("templates") or
            (resp_data.get("data", {}).get("items") if isinstance(resp_data.get("data"), dict) else None) or
            (resp_data.get("data", {}).get("ticket_templates") if isinstance(resp_data.get("data"), dict) else None) or
            (resp_data.get("data") if isinstance(resp_data.get("data"), list) else None) or
            []
        )
    return True, templates, f"Successfully fetched {len(templates)} ticket template(s)."

def convert_templates_to_tsv(templates_list):
    """
    Converts a list of template objects into a ready-to-copy standard TSV string.
    Format:
        Template: Complaint Ticket (#1024)
        VIN\ttrue
        Car Model\tfalse
    """
    if not templates_list:
        return ""

    blocks = []
    for tpl in templates_list:
        if not isinstance(tpl, dict):
            continue
        tpl_name = str(tpl.get("name") or "Unnamed Template").strip()
        tpl_id = tpl.get("id") or tpl.get("ticket_template_id")
        header = f"Template: {tpl_name}"
        if tpl_id:
            header += f" (#{tpl_id})"

        lines = [header]
        fields = tpl.get("fields") or []
        for f in fields:
            if not isinstance(f, dict):
                continue
            title = str(f.get("title") or f.get("name") or "").strip()
            if not title:
                continue
            is_req = bool(f.get("required") or f.get("is_required", False))
            lines.append(f"{title}\t{str(is_req).lower()}")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)

def update_ticket_templates_stream(auth_data, templates_list, tenant_fields_data=None):
    """
    Generator yielding NDJSON streaming events for updating existing ticket templates.
    Overwrites the template's fields with the provided mapped fields array.
    """
    base_url = auth_data.get("base_url", "").rstrip('/')
    if not base_url:
        yield json.dumps({"status": "error", "message": "Missing base URL in Auth Data."}) + "\n"
        return

    total_templates = len(templates_list)
    if total_templates == 0:
        yield json.dumps({"status": "error", "message": "No templates provided to update."}) + "\n"
        return

    yield json.dumps({"status": "info", "message": "Fetching live tenant templates to resolve target IDs..."}) + "\n"
    succ, live_templates, msg = fetch_live_templates(auth_data)
    if not succ:
        yield json.dumps({"status": "error", "message": f"Cannot update templates: {msg}"}) + "\n"
        return

    # Build lookup maps for live templates
    live_id_map = {}
    live_name_map = {}
    for lt in live_templates:
        if isinstance(lt, dict):
            lt_id = lt.get("id") or lt.get("ticket_template_id")
            lt_name = str(lt.get("name", "")).strip()
            if lt_id is not None:
                live_id_map[str(lt_id)] = lt
            if lt_name:
                live_name_map[lt_name.lower()] = lt

    # Fetch tenant ticket fields for validation if not provided
    from core.fields import fetch_custom_fields
    if not tenant_fields_data:
        yield json.dumps({"status": "info", "message": "Fetching live ticket fields for validation..."}) + "\n"
        success, data, f_msg = fetch_custom_fields(auth_data, field_owner="Ticket")
        if not success:
            yield json.dumps({"status": "error", "message": f"Failed to fetch tenant fields: {f_msg}"}) + "\n"
            return
        tenant_fields_data = data.get("fields_json", {})

    # Strict Guard Validation
    is_valid, matched_map, missing_by_template, duplicate_notices = validate_template_fields(templates_list, tenant_fields_data)
    if not is_valid:
        error_details = []
        for t_name, missing in missing_by_template.items():
            error_details.append(f"• [{t_name}]: Missing {len(missing)} field(s): {', '.join(missing)}")
        err_msg = "Strict Guard Failed: Cannot update templates because some referenced fields do not exist in tenant:\n" + "\n".join(error_details)
        yield json.dumps({
            "status": "error",
            "message": err_msg,
            "data": {"missing_by_template": missing_by_template}
        }) + "\n"
        return

    if duplicate_notices:
        dup_msgs = []
        for d_title, d_ids in duplicate_notices.items():
            dup_msgs.append(f"Field '{d_title}' matches multiple tenant fields with identical title (IDs: {', '.join(d_ids)}). Matched ID #{d_ids[0]}.")
        yield json.dumps({
            "status": "info",
            "message": "Duplicate Notice:\n" + "\n".join(dup_msgs)
        }) + "\n"

    yield json.dumps({"status": "info", "message": f"Validation passed! Beginning update for {total_templates} template(s)..."}) + "\n"

    success_count = 0
    failed_count = 0

    for idx, tpl in enumerate(templates_list, 1):
        tpl_name = tpl.get("name", f"Template_{idx}")
        raw_fields = tpl.get("fields", [])

        # Extract target ID: from header or from live template name matching
        target_template_id = None
        target_live_template = None

        # Check explicit ID from header
        m_id = re.search(r'#(\d+)', tpl_name)
        if m_id:
            cand_id = m_id.group(1)
            if cand_id in live_id_map:
                target_template_id = cand_id
                target_live_template = live_id_map[cand_id]

        if not target_template_id:
            # Check clean name without (#id)
            clean_name = re.sub(r'[\(\[]\s*#?\d+\s*[\)\]]', '', tpl_name).strip()
            clean_name = re.sub(r'#\d+', '', clean_name).strip()
            if clean_name.lower() in live_name_map:
                target_live_template = live_name_map[clean_name.lower()]
                target_template_id = target_live_template.get("id") or target_live_template.get("ticket_template_id")
            elif tpl_name.lower() in live_name_map:
                target_live_template = live_name_map[tpl_name.lower()]
                target_template_id = target_live_template.get("id") or target_live_template.get("ticket_template_id")

        if not target_template_id:
            failed_count += 1
            err_msg = f"Template '{tpl_name}' was not found in tenant. Cannot update non-existent template. (To create a new template, use 'Create Ticket Templates')."
            yield json.dumps({
                "status": "error",
                "message": f"[{idx}/{total_templates}] {err_msg}",
                "data": {"index": idx, "name": tpl_name, "status": "not_found"}
            }) + "\n"
            continue

        # Build mapped fields array
        mapped_fields = []
        for f in raw_fields:
            title = f.get("title", "").strip()
            target_id = str(f.get("target_id", "")).strip()
            target_name = str(f.get("target_name", "")).strip().lower()
            resolved_id = str(f.get("resolved_id", "")).strip()

            field_info = (
                (matched_map.get(resolved_id) if resolved_id else None) or
                (matched_map.get(target_id) if target_id else None) or
                (matched_map.get(target_name) if target_name else None) or
                matched_map.get(title) or
                matched_map.get(title.lower())
            )
            if field_info:
                f_id = field_info.get("field_id") or field_info.get("id")
                f_type = field_info.get("field_type")
                if not f_type:
                    ctype = str(field_info.get("content_type", "")).lower()
                    if "drop" in ctype or "select" in ctype:
                        f_type = "DropListField"
                    elif "numeric" in ctype or "number" in ctype:
                        f_type = "NumericField"
                    elif "date" in ctype:
                        f_type = "DateField"
                    else:
                        f_type = "TextField"

                f_name = field_info.get("name") or f"{f_type}_{f_id}"
                is_req = bool(f.get("required", False))

                field_entry = {
                    "id": f_name,
                    "name": f_name,
                    "field_id": int(f_id) if str(f_id).isdigit() else f_id,
                    "field_type": f_type,
                    "content_type": field_info.get("content_type", "text"),
                    "title": field_info.get("title", title),
                    "comment": field_info.get("comment", ""),
                    "is_required": is_req,
                    "required": is_req
                }
                mapped_fields.append(field_entry)

        # Merge with existing template description & settings if available
        desc = tpl.get("description") or (target_live_template.get("description") if target_live_template else "") or ""
        resolved_name = target_live_template.get("name") if target_live_template else tpl_name
        clean_name = re.sub(r'[\(\[]\s*#?\d+\s*[\)\]]', '', tpl_name).strip()
        if clean_name and not clean_name.isdigit():
            resolved_name = clean_name

        payload = {
            "ticket_template": {
                "id": int(target_template_id) if str(target_template_id).isdigit() else target_template_id,
                "name": resolved_name,
                "description": desc,
                "use_scope_type": target_live_template.get("use_scope_type", "all_agents") if target_live_template else "all_agents",
                "use_scope_content": target_live_template.get("use_scope_content", []) if target_live_template else [],
                "email_support_api": True,
                "default": bool(target_live_template.get("default", False)) if target_live_template else False,
                "template_rule_enable": bool(target_live_template.get("template_rule_enable", False)) if target_live_template else False,
                "fields": mapped_fields
            }
        }

        yield json.dumps({
            "status": "progress",
            "message": f"[{idx}/{total_templates}] Updating template '{resolved_name}' (ID: {target_template_id}) with {len(mapped_fields)} field(s)...",
            "data": {"index": idx, "name": resolved_name, "id": target_template_id, "fields_count": len(mapped_fields)}
        }) + "\n"

        update_url = f"{base_url}/cs/ts/api/ticket_templates/{target_template_id}"
        update_resp = execute_request(update_url, 'PUT', payload, auth_data)

        if update_resp.get("status") in [200, 201]:
            resp_data = update_resp.get("data", {})
            if isinstance(resp_data, dict) and resp_data.get("code") not in [None, 1000, 200, 201]:
                failed_count += 1
                err_detail = resp_data.get("message") or resp_data.get("error") or str(resp_data)
                yield json.dumps({
                    "status": "error",
                    "message": f"[{idx}/{total_templates}] Failed to update template '{resolved_name}': {err_detail}",
                    "data": {"index": idx, "name": resolved_name, "id": target_template_id, "status": "failed", "error": err_detail}
                }) + "\n"
            else:
                success_count += 1
                yield json.dumps({
                    "status": "info",
                    "message": f"[{idx}/{total_templates}] Successfully updated template '{resolved_name}' (ID: {target_template_id}) with {len(mapped_fields)} field(s).",
                    "data": {"index": idx, "name": resolved_name, "id": target_template_id, "status": "success"}
                }) + "\n"
        else:
            failed_count += 1
            err_detail = update_resp.get("error") or f"HTTP {update_resp.get('status')}"
            yield json.dumps({
                "status": "error",
                "message": f"[{idx}/{total_templates}] Failed to update template '{resolved_name}': {err_detail}",
                "data": {"index": idx, "name": resolved_name, "id": target_template_id, "status": "failed", "error": err_detail}
            }) + "\n"

        # Rate limiting: 2-second sleep between sequential updates
        if idx < total_templates:
            time.sleep(2)

    summary_msg = f"Ticket template update completed. Total: {total_templates} | Succeeded: {success_count} | Failed: {failed_count}"
    yield json.dumps({
        "status": "done",
        "message": summary_msg,
        "data": {"total": total_templates, "success": success_count, "failed": failed_count}
    }) + "\n"
