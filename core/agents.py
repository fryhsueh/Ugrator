import json
import time
import copy
from core.api import execute_request

def to_id_list(value):
    """
    Safely converts integers, lists, or comma-separated strings of IDs into a list of ints.
    E.g. "1694511, 1694512" -> [1694511, 1694512]
         1694511 -> [1694511]
         [1694511] -> [1694511]
    """
    if value is None:
        return []
    if isinstance(value, list):
        res = []
        for item in value:
            try:
                res.append(int(float(item)))
            except (ValueError, TypeError):
                continue
        return res
    if isinstance(value, (int, float)):
        return [int(value)]
    if isinstance(value, str):
        res = []
        for part in value.replace(';', ',').split(','):
            part = part.strip()
            if part:
                try:
                    res.append(int(float(part)))
                except (ValueError, TypeError):
                    continue
        return res
    return []

KNOWN_PROFILES = {
    "ticket", "工单", "工单客服", "工单员工", "tickets",
    "all", "全渠道", "全渠道员工", "全渠道客服",
    "callcenter", "cc", "呼叫中心", "呼叫中心员工", "呼叫", "电话客服", "外呼员工",
    "im", "chat", "在线客服", "即时通讯", "即时通讯员工", "在线"
}

def normalize_profile(val, default="all"):
    """
    Normalizes account type string to standard Udesk profile values:
    'ticket', 'all', 'callcenter', 'im'.
    Accepts Chinese aliases and case-insensitive variations.
    """
    if val is None or not str(val).strip():
        return default
    v = str(val).strip().lower()

    # Ticket aliases
    if v in ("ticket", "工单", "工单客服", "工单员工", "tickets"):
        return "ticket"
    # Call Center aliases
    if v in ("callcenter", "cc", "呼叫中心", "呼叫中心员工", "呼叫", "电话客服", "外呼员工"):
        return "callcenter"
    # IM aliases
    if v in ("im", "chat", "在线客服", "即时通讯", "即时通讯员工", "在线"):
        return "im"
    # All channels aliases
    if v in ("all", "全渠道", "全渠道员工", "全渠道客服"):
        return "all"

    return v

def fetch_agent_metadata(auth_data):
    """
    Fetches available roles, groups, and departments from the platform tenant.
    Returns: (success: bool, data: dict, message: str)
    """
    base_url = auth_data.get("base_url", "").rstrip('/')
    if not base_url:
        return False, {}, "Missing base URL in Auth Data."

    # 1. Fetch Agent Roles
    roles_url = f"{base_url}/cs/ts/api/agent_roles"
    roles_resp = execute_request(roles_url, 'GET', None, auth_data)
    time.sleep(2)  # Rate limiting

    # 2. Fetch User Groups
    groups_url = f"{base_url}/cs/ts/api/user_groups"
    groups_resp = execute_request(groups_url, 'GET', None, auth_data)
    time.sleep(2)  # Rate limiting

    # 3. Fetch Departments
    depts_url = f"{base_url}/cs/ts/api/departments"
    depts_resp = execute_request(depts_url, 'GET', None, auth_data)

    roles = []
    if roles_resp.get("status") == 200:
        raw_roles = roles_resp.get("data", {}).get("agent_roles", [])
        for r in raw_roles:
            roles.append({
                "id": r.get("id"),
                "name": r.get("name", ""),
                "description": r.get("description", "")
            })

    groups = []
    default_group_id = None
    if groups_resp.get("status") == 200:
        raw_groups = groups_resp.get("data", {}).get("user_groups", [])
        for g in raw_groups:
            gid = g.get("id")
            groups.append({
                "id": gid,
                "name": g.get("name", "")
            })
            if default_group_id is None:
                default_group_id = gid

    departments = []
    default_dept_id = None
    if depts_resp.get("status") == 200:
        raw_depts = depts_resp.get("data", {}).get("departments", [])
        for d in raw_depts:
            did = d.get("id")
            is_def = bool(d.get("is_default", False))
            departments.append({
                "id": did,
                "name": d.get("name", ""),
                "is_default": is_def
            })
            if is_def or default_dept_id is None:
                default_dept_id = did

    result = {
        "roles": roles,
        "groups": groups,
        "departments": departments,
        "default_group_id": default_group_id,
        "default_dept_id": default_dept_id
    }

    if not roles and roles_resp.get("status") != 200:
        return False, result, f"Failed to fetch roles: {roles_resp.get('error') or roles_resp.get('status')}"

    return True, result, f"Loaded {len(roles)} roles and {len(groups)} groups from platform."

def build_agent_payload(agent_item, defaults=None):
    """
    Constructs the JSON payload for creating an individual agent in platform,
    merging per-agent fields with global/template defaults.
    """
    merged_defaults = {
        "password": "Pass2026",
        "profile": "all",
        "agent_role_ids": [1694511],
        "user_group_ids": [1688021],
        "department_ids": [1668261],
        "im_ability_value": "10",
        "agent_invalid": False,
        "valid_email": False,
        "work_id": None,
        "lang": "",
        "user_group_id": None
    }
    if defaults and isinstance(defaults, dict):
        merged_defaults.update(defaults)

    email = str(agent_item.get("email", "")).strip().lower()
    name = str(agent_item.get("name", "")).strip() if agent_item.get("name") else ""
    nick_name = str(agent_item.get("nick_name", "")).strip() if agent_item.get("nick_name") else ""
    password = str(agent_item.get("password") or merged_defaults["password"])
    raw_profile = agent_item.get("profile") or merged_defaults.get("profile", "all")
    profile = normalize_profile(raw_profile, default="all")

    # Resolve ID lists
    role_ids = to_id_list(agent_item.get("agent_role_ids")) or to_id_list(merged_defaults.get("agent_role_ids"))
    group_ids = to_id_list(agent_item.get("user_group_ids")) or to_id_list(merged_defaults.get("user_group_ids"))
    dept_ids = to_id_list(agent_item.get("department_ids")) or to_id_list(merged_defaults.get("department_ids"))
    im_ability = str(agent_item.get("im_ability_value") or merged_defaults.get("im_ability_value") or "10")

    agent_dict = {
        "email": email,
        "profile": profile,
        "password": password,
        "agent_roles": [],
        "agent_role": {},
        "user_group_ids": group_ids,
        "agent_role_ids": role_ids,
        "agent_invalid": bool(agent_item.get("agent_invalid", merged_defaults.get("agent_invalid", False))),
        "im_ability_value": im_ability,
        "department_ids": dept_ids,
        "valid_email": bool(agent_item.get("valid_email", merged_defaults.get("valid_email", False))),
        "work_id": agent_item.get("work_id", merged_defaults.get("work_id")),
        "lang": agent_item.get("lang", merged_defaults.get("lang", "")),
        "user_group_id": agent_item.get("user_group_id", merged_defaults.get("user_group_id"))
    }

    if name:
        agent_dict["name"] = name
    if nick_name:
        agent_dict["nick_name"] = nick_name

    # Cross fallback: if only name is provided, default nick_name to name; if only nick_name is provided, default name to nick_name
    if name and "nick_name" not in agent_dict:
        agent_dict["nick_name"] = name
    elif nick_name and "name" not in agent_dict:
        agent_dict["name"] = nick_name

    if agent_item.get("cellphone"):
        agent_dict["cellphone"] = str(agent_item.get("cellphone")).strip()

    return {"agent": agent_dict}

def parse_agents_text(text_content, default_profile="all", default_role_ids=None):
    """
    Parses multi-line text into a list of agent dicts.
    Supports:
      - Plain email: user@test.com
      - Comma/tab delimited: email, name
      - Comma/tab delimited: email, name, role
      - Comma/tab delimited: email, name, password, role_id
      - Comma/tab delimited: email, name, password, role_id, profile (e.g. ticket, all, callcenter, im)
    Automatically detects and skips header lines.
    """
    agents = []
    if not text_content:
        return agents

    default_prof = normalize_profile(default_profile, default="all")

    lines = text_content.strip().splitlines()
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        delimiter = '\t' if '\t' in line else ','
        parts = [p.strip() for p in line.split(delimiter)]
        email = parts[0]

        # Header detection: skip if it's a header label that does not contain '@'
        if idx == 0 and '@' not in email and any(h in email.lower() for h in ['email', '邮箱', 'agent', 'username', 'user']):
            continue

        if not email or '@' not in email:
            continue

        agent = {
            "email": email.lower(),
            "profile": default_prof
        }
        if default_role_ids:
            agent["agent_role_ids"] = to_id_list(default_role_ids)

        if len(parts) > 1 and parts[1]:
            val1 = parts[1]
            agent["name"] = val1
            agent["nick_name"] = val1

        if len(parts) == 3:
            # If 3 parts, check if part 2 is an explicit account type or a password
            val2 = parts[2]
            if val2.strip().lower() in KNOWN_PROFILES:
                agent["profile"] = normalize_profile(val2, default=agent["profile"])
            else:
                agent["password"] = val2
        elif len(parts) == 4:
            if parts[2]:
                agent["password"] = parts[2]
            if parts[3]:
                val3 = parts[3].strip().lower()
                if val3 in KNOWN_PROFILES:
                    agent["profile"] = normalize_profile(val3, default=agent["profile"])
                else:
                    agent["agent_role_ids"] = to_id_list(parts[3])
        else:
            if len(parts) > 2 and parts[2]:
                agent["password"] = parts[2]
            if len(parts) > 3 and parts[3]:
                agent["agent_role_ids"] = to_id_list(parts[3])
            if len(parts) > 4 and parts[4]:
                agent["profile"] = normalize_profile(parts[4], default=agent["profile"])

        agents.append(agent)

    return agents

def parse_agents_file(file_content_bytes, filename="", default_profile="all", default_role_ids=None):
    """
    Parses an uploaded Excel (.xlsx, .xls) or CSV file into a list of agent dicts.
    Supports smart header detection (matching Email, Name, Nickname, Password, Role, Type/Profile)
    with fallback to column index.
    Returns: (success: bool, agents: list, message: str)
    """
    import io
    import pandas as pd
    try:
        is_csv = filename.lower().endswith('.csv')
        if is_csv:
            try:
                df = pd.read_csv(io.BytesIO(file_content_bytes), header=None, encoding='utf-8-sig')
            except Exception:
                df = pd.read_csv(io.BytesIO(file_content_bytes), header=None, encoding='gbk')
        else:
            df = pd.read_excel(io.BytesIO(file_content_bytes), header=None)

        if df.empty:
            return True, [], "File is empty."

        agents = []
        default_prof = normalize_profile(default_profile, default="all")

        # Smart Header Detection
        header_row_idx = -1
        email_col = -1
        name_col = -1
        nick_col = -1
        pwd_col = -1
        role_col = -1
        profile_col = -1

        # Check first 5 rows for header row
        for r_idx in range(min(5, len(df))):
            row_vals = [str(val).strip().lower() for val in df.iloc[r_idx] if not pd.isna(val)]
            if any(any(h in v for h in ['email', '邮箱', '登录账号', '账号']) for v in row_vals):
                header_row_idx = r_idx
                for c_idx, cell in enumerate(df.iloc[r_idx]):
                    if pd.isna(cell):
                        continue
                    c_str = str(cell).strip().lower()
                    if email_col == -1 and any(h in c_str for h in ['email', '邮箱', '登录账号', '账号']):
                        email_col = c_idx
                    elif nick_col == -1 and any(h in c_str for h in ['昵称', 'nickname', 'nick_name', 'nick']):
                        nick_col = c_idx
                    elif name_col == -1 and any(h in c_str for h in ['姓名', 'name']):
                        name_col = c_idx
                    elif pwd_col == -1 and any(h in c_str for h in ['密码', 'password', '初始密码']):
                        pwd_col = c_idx
                    elif role_col == -1 and any(h in c_str for h in ['角色', 'role', 'role_id']):
                        role_col = c_idx
                    elif profile_col == -1 and any(h in c_str for h in ['员工类型', '账号类型', '客服类型', '类型', 'profile', 'type', 'account_type']):
                        profile_col = c_idx
                break

        if header_row_idx != -1 and email_col != -1:
            # Parse using detected header columns
            for idx in range(header_row_idx + 1, len(df)):
                row = df.iloc[idx]
                if email_col >= len(row) or pd.isna(row[email_col]):
                    continue
                email_val = str(row[email_col]).strip()
                if not email_val or '@' not in email_val:
                    continue

                agent = {
                    "email": email_val.lower(),
                    "profile": default_prof
                }
                if default_role_ids:
                    agent["agent_role_ids"] = to_id_list(default_role_ids)

                name_val = str(row[name_col]).strip() if name_col != -1 and name_col < len(row) and not pd.isna(row[name_col]) else ""
                nick_val = str(row[nick_col]).strip() if nick_col != -1 and nick_col < len(row) and not pd.isna(row[nick_col]) else ""

                if name_val and nick_val:
                    agent["name"] = name_val
                    agent["nick_name"] = nick_val
                elif name_val:
                    agent["name"] = name_val
                    agent["nick_name"] = name_val
                elif nick_val:
                    agent["name"] = nick_val
                    agent["nick_name"] = nick_val

                if pwd_col != -1 and pwd_col < len(row) and not pd.isna(row[pwd_col]):
                    pwd_str = str(row[pwd_col]).strip()
                    if pwd_str:
                        agent["password"] = pwd_str

                if role_col != -1 and role_col < len(row) and not pd.isna(row[role_col]):
                    role_str = str(row[role_col]).strip()
                    if role_str:
                        agent["agent_role_ids"] = to_id_list(role_str)

                if profile_col != -1 and profile_col < len(row) and not pd.isna(row[profile_col]):
                    prof_str = str(row[profile_col]).strip()
                    if prof_str:
                        agent["profile"] = normalize_profile(prof_str, default=default_prof)

                agents.append(agent)
        else:
            # Positional Fallback
            for idx, row in df.iterrows():
                if len(row) == 0 or pd.isna(row[0]):
                    continue
                email_val = str(row[0]).strip()
                if not email_val:
                    continue

                if idx == 0 and any(h in email_val.lower() for h in ['email', '邮箱', 'agent', 'username', 'user']):
                    continue

                if '@' not in email_val:
                    continue

                agent = {
                    "email": email_val.lower(),
                    "profile": default_prof
                }
                if default_role_ids:
                    agent["agent_role_ids"] = to_id_list(default_role_ids)

                if len(row) > 1 and not pd.isna(row[1]) and str(row[1]).strip():
                    val1 = str(row[1]).strip()
                    agent["name"] = val1
                    agent["nick_name"] = val1
                if len(row) > 2 and not pd.isna(row[2]) and str(row[2]).strip():
                    agent["password"] = str(row[2]).strip()
                if len(row) > 3 and not pd.isna(row[3]) and str(row[3]).strip():
                    agent["agent_role_ids"] = to_id_list(str(row[3]).strip())
                if len(row) > 4 and not pd.isna(row[4]) and str(row[4]).strip():
                    agent["profile"] = normalize_profile(str(row[4]).strip(), default=default_prof)

                agents.append(agent)

        return True, agents, f"Successfully parsed {len(agents)} agent(s) from {filename or 'file'}."
    except Exception as e:
        return False, [], f"Failed to parse file: {e}"

def create_agents_stream(auth_data, agents_list, defaults=None):
    """
    Generator that creates agents one-by-one via platform API.
    Yields JSON string lines for real-time progress reporting.
    Adheres strictly to the 2-second rate-limiting delay between sequential requests.
    """
    base_url = auth_data.get("base_url", "").rstrip('/')
    if not base_url:
        yield json.dumps({"status": "error", "message": "Error: Missing base URL in Auth Data."}) + "\n"
        return

    if not agents_list:
        yield json.dumps({"status": "error", "message": "Error: No agent records provided."}) + "\n"
        return

    endpoint = f"{base_url}/cs/ts/api/agents"
    total = len(agents_list)
    success_count = 0
    failed_count = 0

    yield json.dumps({
        "status": "log",
        "message": f"Using endpoint: {endpoint}"
    }) + "\n"
    yield json.dumps({
        "status": "log",
        "message": f"Starting batch creation of {total} Agent(s)..."
    }) + "\n"

    for i, agent_item in enumerate(agents_list):
        email = agent_item.get("email", "").strip()
        if not email:
            failed_count += 1
            yield json.dumps({
                "status": "error",
                "index": i,
                "email": "(empty)",
                "message": f"[{i+1}/{total}] Skipping agent with missing email."
            }) + "\n"
            continue

        payload = build_agent_payload(agent_item, defaults)
        profile_name = payload["agent"].get("profile", "all")
        role_ids = payload["agent"].get("agent_role_ids", [])
        nick_val = payload["agent"].get("nick_name")
        nick_str = f", Nick: {nick_val}" if nick_val else ""
        yield json.dumps({
            "status": "log",
            "message": f"[{i+1}/{total}] Creating agent '{email}'{nick_str} (Type: {profile_name}, Role: {role_ids})..."
        }) + "\n"

        resp = execute_request(endpoint, 'POST', payload, auth_data)
        status = resp.get("status")

        if status in (200, 201):
            data = resp.get("data", {})
            if isinstance(data, dict) and "code" in data and str(data.get("code")) not in ("1000", "200"):
                err_msg = data.get("message") or str(data)
                failed_count += 1
                yield json.dumps({
                    "status": "error",
                    "index": i,
                    "email": email,
                    "message": f"[{i+1}/{total}] Failed to create '{email}': {err_msg}"
                }) + "\n"
            else:
                success_count += 1
                yield json.dumps({
                    "status": "progress",
                    "index": i,
                    "email": email,
                    "success": True,
                    "message": f"[{i+1}/{total}] Successfully created agent '{email}'."
                }) + "\n"
        else:
            failed_count += 1
            err_msg = resp.get("error") or f"HTTP {status}"
            yield json.dumps({
                "status": "error",
                "index": i,
                "email": email,
                "message": f"[{i+1}/{total}] Failed to create '{email}'. Status: {status}. Detail: {err_msg}"
            }) + "\n"

        # Rate-limiting rule: delay 2 seconds between sequential calls
        if i < total - 1:
            time.sleep(2)

    yield json.dumps({
        "status": "done",
        "total": total,
        "success_count": success_count,
        "failed_count": failed_count,
        "message": f"Finished agent creation: {success_count} succeeded, {failed_count} failed."
    }) + "\n"
