import json
import urllib.request
import urllib.error
import urllib.parse

def execute_request(url, method, payload, auth_data, content_type="application/json"):
    """
    Executes an HTTP request with proper authentication headers.
    Returns the parsed JSON response or None on failure.
    """
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": f"{content_type};charset=UTF-8" if "charset" not in content_type else content_type,
        "origin": auth_data["base_url"],
        "referer": f"{auth_data['base_url']}/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    if auth_data.get("x_csrf_token"):
        headers["x-csrf-token"] = auth_data["x_csrf_token"]
        
    cookie_str = "; ".join([f"{k}={v}" for k, v in auth_data["cookies"].items()])
    headers["cookie"] = cookie_str
    
    if payload:
        if "application/json" in content_type:
            data = json.dumps(payload).encode('utf-8')
        elif isinstance(payload, str):
            data = payload.encode('utf-8')
        else:
            # e.g., urlencoded dictionary
            data = urllib.parse.urlencode(payload).encode('utf-8')
    else:
        data = None
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            resp_body = response.read().decode('utf-8')
            return {"status": response.status, "data": json.loads(resp_body) if resp_body else {}}
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode('utf-8')
        print(f"Failed with status code {e.code}.")
        print(f"Response: {resp_body}")
        return {"status": e.code, "error": resp_body}
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {"status": 500, "error": str(e)}
