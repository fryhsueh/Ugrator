"""
[LEGACY] Ugrator Platform Toolkit - Command Line Interface (CLI)

DEPRECATION NOTICE:
This CLI (migrator.py) is marked as LEGACY and is no longer updated or maintained.
All active features, interactive workflows, real-time streaming logs, and automation
(Tickets, Agents, Voice Library, IVR Canvas Builder) are centralized in the Web UI:
    Start via: start_migrator.bat  OR  python server.py (http://localhost:8081)
"""
import argparse
import json
import os
import sys
from core.auth import get_auth_config
from core.fields import process_fields, delete_fields
from core.templates import migrate_template
from core.groups import create_agent_groups
from core.voice import scan_voice_files, upload_voice_stream

def main():
    print("=" * 75, file=sys.stderr)
    print("[NOTICE] migrator.py is a LEGACY interface and will not receive future updates.", file=sys.stderr)
    print("         Please use the Web UI instead: run start_migrator.bat or python server.py", file=sys.stderr)
    print("=" * 75, file=sys.stderr)

    parser = argparse.ArgumentParser(
        description="[LEGACY] Ugrator Platform Toolkit - CLI (Web UI via server.py / start_migrator.bat is recommended)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands (Legacy)")

    # Fields Migration Command
    parser_fields_migrate = subparsers.add_parser("fields-migrate", help="Create custom fields in Tenant B from raw JSON.")
    parser_fields_migrate.add_argument("--source", required=True, help="Path to raw.json (Tenant A export)")
    parser_fields_migrate.add_argument("--auth", required=True, help="Path to PowerShell auth script from Tenant B")
    
    # Fields Deletion Command
    parser_fields_delete = subparsers.add_parser("fields-delete", help="Delete custom fields based on a JSON export.")
    parser_fields_delete.add_argument("--source", required=True, help="Path to delete.json export")
    parser_fields_delete.add_argument("--auth", required=True, help="Path to PowerShell auth script from Tenant B")

    # Template Migration Command
    parser_template_migrate = subparsers.add_parser("template-migrate", help="Automate complete template mapping and creation.")
    parser_template_migrate.add_argument("--template-config", required=True, help="Path to Tenant A's template JSON")
    parser_template_migrate.add_argument("--fields-map", required=True, help="Path to Tenant B's new custom fields JSON")
    parser_template_migrate.add_argument("--auth", required=True, help="Path to PowerShell auth script from Tenant B")

    # Agent Groups Command
    parser_agent_groups = subparsers.add_parser("agent-groups", help="Create Agent Groups from a list of names.")
    parser_agent_groups.add_argument("--names", required=True, help="Path to a text file containing group names (one per line)")
    parser_agent_groups.add_argument("--auth", required=True, help="Path to PowerShell auth script for creating a group")

    # Voice Upload Command
    parser_voice = subparsers.add_parser("voice-upload", help="Upload voice files to Voice File Library via Playwright CDP.")
    parser_voice.add_argument("--dir", help="Directory of audio files to upload")
    parser_voice.add_argument("--file", help="Single audio file to upload")
    parser_voice.add_argument("--auth", help="Path to PowerShell auth script (optional, for domain extraction)")
    parser_voice.add_argument("--naming-mode", default="folder_suffix", choices=["folder_suffix", "exact", "prefix", "suffix", "custom"], help="Voice naming mode")
    parser_voice.add_argument("--prefix", default="", help="Prefix string for voice names")
    parser_voice.add_argument("--suffix", default="", help="Suffix string for voice names")
    parser_voice.add_argument("--pattern", default="", help="Custom pattern, e.g. '{prefix}_{file}_{folder}'")
    parser_voice.add_argument("--port", type=int, default=9225, help="Chrome CDP port (default: 9225)")
    parser_voice.add_argument("--cdp-url", help="Direct WebSocket URL for CDP connection")
    parser_voice.add_argument("--url", help="Target Voice List URL")
    parser_voice.add_argument("--username", help="Login username for auto-login")
    parser_voice.add_argument("--password", help="Login password for auto-login")

    # Command: ivr-build
    parser_ivr = subparsers.add_parser("ivr-build", help="Build and link an IVR flow on Call Center canvas from YAML/JSON")
    parser_ivr.add_argument("--file", required=True, help="Path to IVR YAML or JSON workflow definition file")
    parser_ivr.add_argument("--port", type=int, default=9225, help="Chrome CDP port (default: 9225)")
    parser_ivr.add_argument("--cdp-url", help="Direct WebSocket URL for CDP connection")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Load Authentication if needed
    auth_data = None
    if getattr(args, "auth", None):
        print("Parsing Authentication...")
        auth_data = get_auth_config(args.auth)
        if not auth_data and args.command != "voice-upload":
            print("Authentication failed. Aborting.")
            return

    # Execute Command
    if args.command == "fields-migrate":
        templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        process_fields(auth_data, args.source, templates_dir)
        
    elif args.command == "fields-delete":
        delete_fields(auth_data, args.source)
        
    elif args.command == "template-migrate":
        try:
            with open(args.template_config, 'r', encoding='utf-8') as f:
                template_payload = json.load(f)
            with open(args.fields_map, 'r', encoding='utf-8') as f:
                fields_data = json.load(f)
            migrate_template(auth_data, template_payload, fields_data)
        except FileNotFoundError as e:
            print(f"Error: {e}")
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
        
    elif args.command == "agent-groups":
        try:
            with open(args.names, 'r', encoding='utf-8') as f:
                names = f.read().splitlines()
            create_agent_groups(auth_data, names)
        except Exception as e:
            print(f"Error reading names file: {e}")

    elif args.command == "voice-upload":
        files_to_upload = []
        if args.file:
            if not os.path.exists(args.file):
                print(f"Error: File not found: {args.file}")
                return
            filename = os.path.basename(args.file)
            parent_dir = os.path.basename(os.path.dirname(os.path.abspath(args.file)))
            from core.voice import generate_voice_name
            v_name = generate_voice_name(filename, parent_dir, args.naming_mode, args.prefix, args.suffix, args.pattern)
            files_to_upload.append({
                "path": os.path.abspath(args.file),
                "filename": filename,
                "voice_name": v_name
            })
        elif args.dir:
            success, result = scan_voice_files(args.dir, args.naming_mode, args.prefix, args.suffix, args.pattern)
            if not success:
                print(f"Error scanning directory: {result}")
                return
            files_to_upload = result
        else:
            print("Error: You must provide either --dir or --file")
            return

        if not files_to_upload:
            print("No audio files found to upload.")
            return

        custom_creds = None
        if args.username and args.password:
            custom_creds = {"username": args.username, "password": args.password}

        for chunk in upload_voice_stream(
            files_to_upload=files_to_upload,
            cdp_port=args.port,
            cdp_url=args.cdp_url,
            target_url=args.url,
            auth_data=auth_data,
            custom_creds=custom_creds
        ):
            try:
                msg_data = json.loads(chunk)
                print(f"[{msg_data.get('status', 'info').upper()}] {msg_data.get('message', '')}")
            except Exception:
                print(chunk.strip())

    elif args.command == "ivr-build":
        from core.ivr import parse_ivr_workflow, build_ivr_stream
        if not os.path.exists(args.file):
            print(f"Error: IVR workflow file '{args.file}' not found.")
            return

        with open(args.file, "r", encoding="utf-8") as f:
            workflow_content = f.read()

        validation = parse_ivr_workflow(workflow_content)
        if not validation["valid"]:
            print(f"Workflow Validation Error: {validation['error']}")
            return

        print(f"Workflow '{validation.get('ivr_name')}' validated successfully ({len(validation['nodes'])} nodes).")
        print(f"Referenced voices: {', '.join(validation['referenced_voices']) or 'None'}")
        print("Starting IVR canvas automation...")

        for chunk in build_ivr_stream(
            workflow_content=workflow_content,
            cdp_port=args.port,
            cdp_url=args.cdp_url
        ):
            try:
                msg_data = json.loads(chunk)
                print(f"[{msg_data.get('status', 'info').upper()}] {msg_data.get('message', '')}")
            except Exception:
                print(chunk.strip())

if __name__ == "__main__":
    main()
