import re
import json

def parse_auth_string(script_content):
    """
    Parses a PowerShell script string (e.g. copied from Chrome DevTools) to extract 
    the base URL, cookies, x-csrf-token, the target Template ID, and the JSON body payload.
    """
    auth_data = {"cookies": {}}
    
    # Extract base url, full path, and Template ID if present
    uri_match = re.search(r'-Uri\s+[\'"](https://[^/\'"]+)(.*?)[\'"]', script_content)
    if uri_match:
        auth_data["base_url"] = uri_match.group(1)
        full_path = uri_match.group(2)
        auth_data["full_path"] = full_path
        # Check if the path ends with a numeric ID (e.g. /cs/ts/api/ticket_templates/2710)
        id_match = re.search(r'/ticket_templates/(\d+)', full_path)
        if id_match:
            auth_data["template_id"] = int(id_match.group(1))
    else:
        return None, "Could not find base URL (-Uri) in the script. Did you drag the correct file? Please ensure it is a 'Copy as PowerShell' script and not a JSON file or cURL command."
        
    # Extract JSON Body if present
    # PowerShell strings are typically like -Body "{...}" or -Body '{...}'
    # Or encoded: -Body ([System.Text.Encoding]::UTF8.GetBytes("{...}"))
    
    body_match = re.search(r'-Body\s+\(\[System\.Text\.Encoding\]::UTF8\.GetBytes\(([\'"].*?[\'"])\)\)', script_content, re.DOTALL)
    if not body_match:
        body_match = re.search(r'-Body\s+(".*?}")', script_content, re.DOTALL)
    if not body_match:
        body_match = re.search(r"-Body\s+('.*?}')", script_content, re.DOTALL)
        
    if body_match:
        body_str = body_match.group(1)
        # Remove the outer quotes
        body_str = body_str[1:-1]
        # Unescape PowerShell double quotes if any (`")
        body_str = body_str.replace('`"', '"')
        auth_data["body_raw"] = body_str
        try:
            auth_data["body_json"] = json.loads(body_str)
        except Exception as e:
            print(f"JSON Parse Error: {e}")
            pass # Not fatal, it just might not be valid JSON or might not be a POST/PUT
            
    # Extract x-csrf-token from headers
    csrf_match = re.search(r'"x-csrf-token"\s*=\s*"([^"]+)"', script_content, re.IGNORECASE)
    if csrf_match:
        auth_data["x_csrf_token"] = csrf_match.group(1)
    else:
        auth_data["x_csrf_token"] = ""
        
    # Extract cookies
    cookie_matches = re.finditer(r'System\.Net\.Cookie\("([^"]+)",\s*"([^"]+)"', script_content)
    for match in cookie_matches:
        cookie_name = match.group(1)
        cookie_value = match.group(2)
        # Remove PowerShell escaping from the string
        cookie_value = cookie_value.replace('`$', '$')
        auth_data["cookies"][cookie_name] = cookie_value
        
    if not auth_data["cookies"]:
        return None, "Could not find any cookies in the script."
        
    return auth_data, None

def get_auth_config(auth_file):
    try:
        with open(auth_file, 'r', encoding='utf-8') as f:
            script_content = f.read()
        
        auth_data, err = parse_auth_string(script_content)
        if err:
            print(f"Error: {err}")
        return auth_data
    except Exception as e:
        print(f"Error parsing {auth_file}: {e}")
        return None
