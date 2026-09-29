import json
import time
from core.api import execute_request

def update_name_in_payload(obj, new_name):
    """
    Recursively search for a dictionary containing a 'name' key and update it.
    This handles varying structures like {"user_group": {"name": "test"}} 
    or just {"name": "test"}.
    """
    if isinstance(obj, dict):
        # We assume the first 'name' key we find is the target for the group name
        # to handle any arbitrary payload structure (user_group, agent_group, etc.)
        if "name" in obj:
            obj["name"] = new_name
            return True
        for key, value in obj.items():
            if update_name_in_payload(value, new_name):
                return True
    elif isinstance(obj, list):
        for item in obj:
            if update_name_in_payload(item, new_name):
                return True
    return False

def create_agent_groups_data_stream(auth_data, group_names):
    """
    Creates multiple Agent Groups based on a list of names.
    Yields JSON string lines for real-time progress reporting.
    """
    base_url = auth_data.get("base_url")
    full_path = auth_data.get("full_path", "")
    original_payload = auth_data.get("body_json")
    
    if not base_url:
        yield json.dumps({"status": "error", "message": "Error: Missing base URL in Auth Data."}) + "\n"
        return
    
    # Default endpoint and payload for creating agent groups,
    # in case the Global Auth script doesn't contain them.
    if not full_path or "user_groups" not in full_path:
        full_path = "/cs/ts/api/user_groups"
        
    if not original_payload:
        original_payload = {"user_group": {"name": "placeholder"}}
        
    if not group_names:
        yield json.dumps({"status": "error", "message": "Error: No group names provided."}) + "\n"
        return

    endpoint = f"{base_url.rstrip('/')}{full_path}"
    yield json.dumps({"status": "log", "message": f"Using endpoint: {endpoint}"}) + "\n"
    yield json.dumps({"status": "log", "message": f"Starting creation of {len(group_names)} Agent Groups..."}) + "\n"
    
    success_count = 0
    for name in group_names:
        name = name.strip()
        if not name:
            continue
            
        payload_copy = json.loads(json.dumps(original_payload))
        
        updated = update_name_in_payload(payload_copy, name)
        if not updated:
            yield json.dumps({"status": "error", "message": "Error: Could not find a 'name' field in the JSON payload to update."}) + "\n"
            return
            
        yield json.dumps({"status": "log", "message": f"Creating group: '{name}'..."}) + "\n"
        
        resp = execute_request(endpoint, 'POST', payload_copy, auth_data)
        
        if resp.get("status") in (200, 201):
            resp_data = resp.get("data", {})
            if isinstance(resp_data, dict) and "code" in resp_data and str(resp_data.get("code")) != "1000":
                yield json.dumps({"status": "error", "message": f"Failed to create '{name}'. API responded with: {resp_data}"}) + "\n"
                return
                
            yield json.dumps({"status": "log", "message": f"Successfully created '{name}'."}) + "\n"
            success_count += 1
            time.sleep(2)
        else:
            yield json.dumps({"status": "error", "message": f"Failed to create '{name}'. Status: {resp.get('status')}. Response: {resp.get('error')}"}) + "\n"
            return
            
    yield json.dumps({"status": "done", "message": f"Finished. Successfully created {success_count} groups."}) + "\n"

def create_agent_groups(auth_data, group_names):
    # Fallback for CLI, consume the stream and print
    success = False
    for chunk in create_agent_groups_data_stream(auth_data, group_names):
        try:
            data = json.loads(chunk.strip())
            print(data["message"])
            if data["status"] == "done":
                success = True
        except:
            print(chunk.strip())
    return success
