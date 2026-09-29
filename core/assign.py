import json
import time
from core.api import execute_request

def extract_mapping(data, key_field, val_field, mapping):
    """
    Recursively search JSON data for objects containing both key_field and val_field
    and populate the mapping dict.
    """
    if isinstance(data, dict):
        if key_field in data and val_field in data:
            # key could be a string (name/email), val is the ID
            key_str = str(data[key_field]).strip()
            if key_field == "email":
                key_str = key_str.lower()
            val = data[val_field]
            if key_str:
                mapping[key_str] = val
        for v in data.values():
            extract_mapping(v, key_field, val_field, mapping)
    elif isinstance(data, list):
        for item in data:
            extract_mapping(item, key_field, val_field, mapping)

def assign_agents_stream(auth_data, groups_json_str, agents_json_str, mapping_csv_str):
    """
    Generator that parses JSON mappings and assigns agents to groups via bulk API calls.
    Yields JSON string lines for real-time progress reporting.
    """
    try:
        groups_data = json.loads(groups_json_str)
        agents_data = json.loads(agents_json_str)
    except Exception as e:
        yield json.dumps({"status": "error", "message": f"Error parsing JSON inputs: {e}"}) + "\n"
        return

    # Build Mappings
    group_mapping = {}  # name -> id
    agent_mapping = {}  # email -> id
    
    extract_mapping(groups_data, "name", "id", group_mapping)
    # Sometimes groups are embedded in agent data, try extracting from there too as fallback
    extract_mapping(agents_data, "name", "id", group_mapping) 
    extract_mapping(agents_data, "email", "id", agent_mapping)

    yield json.dumps({"status": "log", "message": f"Parsed {len(group_mapping)} groups and {len(agent_mapping)} agents from JSON."}) + "\n"

    # Parse CSV Mapping
    # Expected format: Agent Email, Group1, Group2, ...
    assignments = {} # group_name -> list of agent_emails
    
    for line in mapping_csv_str.splitlines():
        line = line.strip()
        if not line or ',' not in line:
            continue
        
        # Skip common header patterns
        first_col = line.split(',')[0].strip().lower()
        if first_col in ('email', 'agent', 'agent email', 'agent_email', 'user', 'user email'):
            continue
        
        parts = [p.strip() for p in line.split(',') if p.strip()]
        if len(parts) < 2:
            continue
            
        a_email = parts[0].lower()
        g_names = parts[1:]
        
        for g_name in g_names:
            if g_name not in assignments:
                assignments[g_name] = []
            assignments[g_name].append(a_email)

    if not assignments:
        yield json.dumps({"status": "error", "message": "No valid mappings found in the CSV. Use format: Agent Email, Group1, Group2..."}) + "\n"
        return

    base_url = auth_data.get("base_url", "").rstrip('/')
    if not base_url:
        yield json.dumps({"status": "error", "message": "Missing base URL in Auth Script."}) + "\n"
        return

    yield json.dumps({"status": "log", "message": f"Starting assignment for {len(assignments)} groups..."}) + "\n"
    
    success_count = 0
    
    for g_name, agent_emails in assignments.items():
        if g_name not in group_mapping:
            yield json.dumps({"status": "error", "message": f"Group '{g_name}' not found in Groups JSON. Skipping."}) + "\n"
            continue
            
        group_id = group_mapping[g_name]
        
        # Collect agent IDs
        agent_ids = []
        for email in agent_emails:
            if email in agent_mapping:
                agent_ids.append(agent_mapping[email])
            else:
                yield json.dumps({"status": "error", "message": f"Agent '{email}' not found in Agents JSON. Skipping this agent."}) + "\n"
                
        if not agent_ids:
            yield json.dumps({"status": "error", "message": f"No valid agents to assign to group '{g_name}'."}) + "\n"
            continue
            
        # Prepare endpoint and payload
        # PowerShell script endpoint format: /cs/ts/api/user_groups/{group_id}/add_agent
        endpoint = f"{base_url}/cs/ts/api/user_groups/{group_id}/add_agent"
        
        # Payload format: user_ids[]=16118&user_ids[]=16119
        payload = []
        for a_id in agent_ids:
            payload.append(("user_ids[]", a_id))
            
        yield json.dumps({"status": "log", "message": f"Assigning {len(agent_ids)} agents to group '{g_name}' (ID: {group_id})..."}) + "\n"
        
        resp = execute_request(endpoint, 'POST', payload, auth_data, content_type="application/x-www-form-urlencoded")
        
        if resp.get("status") in (200, 201):
            resp_data = resp.get("data", {})
            if isinstance(resp_data, dict) and "code" in resp_data and str(resp_data.get("code")) != "1000":
                yield json.dumps({"status": "error", "message": f"Failed for '{g_name}'. API responded with: {resp_data}"}) + "\n"
                continue
                
            yield json.dumps({"status": "log", "message": f"Successfully assigned agents to '{g_name}'."}) + "\n"
            success_count += 1
            time.sleep(2)  # Delay to prevent rate limiting
        else:
            yield json.dumps({"status": "error", "message": f"Failed for '{g_name}'. Status: {resp.get('status')}. Response: {resp.get('error')}"}) + "\n"
            continue
            
    yield json.dumps({"status": "done", "message": f"Finished. Successfully processed {success_count} groups."}) + "\n"

def assign_agents_to_groups(groups_json_str, agents_json_str, mapping_csv_str, auth_data):
    """
    Non-streaming helper for CLI or backward-compatibility.
    """
    last_msg = ""
    success = False
    for chunk in assign_agents_stream(auth_data, groups_json_str, agents_json_str, mapping_csv_str):
        try:
            data = json.loads(chunk.strip())
            last_msg = data.get("message", last_msg)
            if data.get("status") == "done":
                success = True
        except Exception:
            pass
    return success, last_msg

def fetch_groups_and_agents(auth_data):
    """
    Fetches user groups and agents from platform API using auth credentials.
    Returns: (success, result_dict, message)
    """
    base_url = auth_data.get("base_url", "").rstrip('/')
    if not base_url:
        return False, {}, "Missing base URL in Auth Data."

    groups_url = f"{base_url}/cs/ts/api/user_groups"
    groups_resp = execute_request(groups_url, 'GET', None, auth_data)

    time.sleep(2)  # Delay to prevent rate limiting

    agents_url = f"{base_url}/cs/ts/api/agents"
    agents_resp = execute_request(agents_url, 'GET', None, auth_data)

    groups_json = groups_resp.get("data", {}) if groups_resp.get("status") == 200 else {}
    agents_json = agents_resp.get("data", {}) if agents_resp.get("status") == 200 else {}

    messages = []
    if groups_resp.get("status") != 200:
        messages.append(f"Failed to fetch groups (status {groups_resp.get('status')})")
    if agents_resp.get("status") != 200:
        messages.append(f"Failed to fetch agents (status {agents_resp.get('status')})")

    if messages:
        return False, {"groups_json": groups_json, "agents_json": agents_json}, "; ".join(messages)

    groups_count = len(groups_json.get("user_groups", []))
    agents_count = len(agents_json.get("agents", []))
    msg = f"Fetched {groups_count} groups and {agents_count} agents."
    return True, {"groups_json": groups_json, "agents_json": agents_json}, msg

