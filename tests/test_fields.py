import unittest
import os
import json
from unittest.mock import patch
import core.fields
from core.fields import migrate_fields, process_fields_data, fetch_custom_fields, create_custom_fields_stream, migrate_fields_stream

class TestFieldsModule(unittest.TestCase):
    def test_migrate_fields_invalid_json(self):
        auth_data = {"base_url": "https://test.desk-platform.com"}
        success, msg = migrate_fields("not valid json", auth_data)
        self.assertFalse(success)
        self.assertIn("Invalid JSON", msg)

    def test_migrate_fields_execution(self):
        auth_data = {
            "base_url": "https://test.desk-platform.com",
            "cookies": {},
            "x_csrf_token": "token"
        }
        raw_data = {
            "ticketFields": [
                {"title": "Custom Text", "content_type": "text"}
            ]
        }

        with patch("core.fields.execute_request", return_value={"status": 200}), patch("time.sleep", return_value=None):
            success, msg = migrate_fields(raw_data, auth_data)
            self.assertTrue(success)
            self.assertIn("Field migration completed", msg)

    def test_migrate_fields_stream_progress(self):
        auth_data = {
            "base_url": "https://test.desk-platform.com",
            "cookies": {},
            "x_csrf_token": "token"
        }
        raw_data = {
            "ticketFields": [
                {"title": "Custom Dropdown", "content_type": "droplist"}
            ]
        }

        with patch("core.fields.execute_request", return_value={"status": 200}), patch("time.sleep", return_value=None):
            events = [json.loads(line) for line in migrate_fields_stream(raw_data, auth_data)]
            statuses = [e["status"] for e in events]
            self.assertIn("system", statuses)
            self.assertIn("progress", statuses)
            self.assertIn("done", statuses)
            progress_event = next(e for e in events if e["status"] == "progress")
            self.assertIn("Processing field: Custom Dropdown", progress_event["message"])

    def test_fetch_custom_fields_missing_base_url(self):
        auth_data = {"base_url": ""}
        success, data, msg = fetch_custom_fields(auth_data)
        self.assertFalse(success)
        self.assertIn("Missing base URL", msg)

    def test_fetch_custom_fields_error_response(self):
        auth_data = {"base_url": "https://test.desk-platform.com"}
        with patch("core.fields.execute_request", return_value={"status": 401, "error": "Unauthorized"}):
            success, data, msg = fetch_custom_fields(auth_data)
            self.assertFalse(success)
            self.assertIn("Failed to fetch custom fields", msg)

    def test_fetch_custom_fields_success(self):
        auth_data = {"base_url": "https://test.desk-platform.com"}
        mock_response = {
            "status": 200,
            "data": {
                "custom_fields": [
                    {"id": 1, "title": "Field A", "content_type": "text"},
                    {"id": 2, "title": "Field B", "content_type": "droplist"},
                    {"id": 3, "title": "Field C", "content_type": "text"}
                ]
            }
        }
        with patch("core.fields.execute_request", return_value=mock_response):
            success, data, msg = fetch_custom_fields(auth_data)
            self.assertTrue(success)
            self.assertEqual(data["count"], 3)
            self.assertEqual(data["stats"], {"text": 2, "droplist": 1})
            self.assertIn("ticketFields", data["fields_json"])
            self.assertIn("custom_fields", data["fields_json"])
            self.assertIn("Successfully fetched 3 custom fields", msg)

    def test_create_custom_fields_stream_missing_base_url(self):
        auth_data = {"base_url": ""}
        stream = core.fields.create_custom_fields_stream(auth_data, [{"title": "T1", "type": "text"}])
        lines = [json.loads(line) for line in stream]
        self.assertEqual(lines[0]["status"], "error")
        self.assertIn("Missing base URL", lines[0]["message"])

    def test_create_custom_fields_stream_success(self):
        auth_data = {"base_url": "https://test.desk-platform.com"}
        fields_to_create = [
            {"title": "Custom Text", "type": "text"},
            {"title": "Custom Date", "type": "date"},
            {"title": "Custom Dropdown", "type": "drop_list", "options": ["Opt1", "Opt2"]}
        ]
        with patch("core.fields.execute_request", return_value={"status": 200}), patch("time.sleep", return_value=None):
            stream = core.fields.create_custom_fields_stream(auth_data, fields_to_create)
            events = [json.loads(line) for line in stream]
            self.assertEqual(events[0]["status"], "start")
            self.assertEqual(events[0]["total"], 3)
            # 3 progress events
            progress_events = [e for e in events if e["status"] == "progress"]
            self.assertEqual(len(progress_events), 3)
            self.assertTrue(all(e["success"] for e in progress_events))
            # 1 done event
            self.assertEqual(events[-1]["status"], "done")
            self.assertEqual(events[-1]["success_count"], 3)

    def test_parse_fields_file_csv(self):
        csv_content = "Field Name,Field Type,Opt A,Opt B\nIssueType,drop_list,Bug,Feature\nStartDate,date\nDescription,text\n".encode('utf-8')
        success, fields, msg = core.fields.parse_fields_file(csv_content, "fields.csv")
        self.assertTrue(success)
        self.assertEqual(len(fields), 3)
        self.assertEqual(fields[0]["title"], "IssueType")
        self.assertEqual(fields[0]["type"], "drop_list")
        self.assertEqual(fields[0]["options"], ["Bug", "Feature"])
        self.assertEqual(fields[1]["title"], "StartDate")
        self.assertEqual(fields[1]["type"], "date")
        self.assertEqual(fields[2]["title"], "Description")
        self.assertEqual(fields[2]["type"], "text")

    def test_create_custom_fields_stream_role_abilities(self):
        auth_data = {"base_url": "https://test.desk-platform.com"}
        fields_to_create = [
            {
                "title": "Distributor Notes",
                "type": "text",
                "persona": "Distributor",
                "invisible_role_ids": [410]
            }
        ]
        all_roles = [
            {"id": 410, "name": "Agent"},
            {"id": 413, "name": "Distributor"}
        ]

        calls = []
        def mock_execute(url, method, payload, auth):
            calls.append({"url": url, "method": method, "payload": payload})
            if "agent_role_abilities" in url:
                return {"status": 200, "data": {}}
            return {"status": 200, "data": {"text_field": {"id": 8888, "field_type": "TextField"}}}

        with patch("core.fields.execute_request", side_effect=mock_execute), patch("time.sleep", return_value=None):
            stream = core.fields.create_custom_fields_stream(auth_data, fields_to_create, all_roles=all_roles)
            events = [json.loads(line) for line in stream]

            # Verify field creation request
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0]["method"], "POST")
            self.assertIn("/cs/ts/api/text_fields", calls[0]["url"])

            # Verify role abilities PUT request
            self.assertEqual(calls[1]["method"], "PUT")
            self.assertIn("/cs/ts/api/fields/8888/agent_role_abilities", calls[1]["url"])
            put_payload = calls[1]["payload"]
            self.assertEqual(put_payload["field_type"], "TextField")
            abilities = put_payload["abilities"]
            self.assertEqual(len(abilities), 2)

            # Role 410 should be invisible
            role_410_entry = next(a for a in abilities if a["agent_role_id"] == 410)
            self.assertEqual(role_410_entry["permission"], "invisible")
            self.assertEqual(role_410_entry["show_permission"], "sensitive")

            # Role 413 should be preset_value
            role_413_entry = next(a for a in abilities if a["agent_role_id"] == 413)
            self.assertEqual(role_413_entry["permission"], "preset_value")
            self.assertEqual(role_413_entry["show_permission"], "default")

            # Verify log event was emitted
            log_events = [e for e in events if e.get("status") == "log"]
            self.assertTrue(any("Configured permissions for 'Distributor Notes'" in e["message"] for e in log_events))

    def test_create_custom_fields_stream_description(self):
        auth_data = {"base_url": "https://test.desk-platform.com"}
        fields_to_create = [
            {"title": "VIN", "type": "text", "description": "Vehicle Identification Number"},
            {"title": "Delivery Date", "type": "date", "description": "Date of handover"},
            {"title": "Model", "type": "drop_list", "options": ["Model Alpha", "Model Beta"], "description": "Product model code"}
        ]
        calls = []
        def mock_execute(url, method, payload, auth):
            calls.append({"url": url, "method": method, "payload": payload})
            return {"status": 200, "data": {}}

        with patch("core.fields.execute_request", side_effect=mock_execute), patch("time.sleep", return_value=None):
            stream = core.fields.create_custom_fields_stream(auth_data, fields_to_create, field_owner="Ticket")
            events = [json.loads(line) for line in stream]
            self.assertEqual(len(calls), 3)
            self.assertEqual(calls[0]["payload"]["text_field"]["comment"], "Vehicle Identification Number")
            self.assertEqual(calls[1]["payload"]["text_field"]["comment"], "Date of handover")
            self.assertEqual(calls[2]["payload"]["select_field"]["comment"], "Product model code")

    def test_parse_fields_file_with_description_and_persona(self):
        # 5-column TSV: Title \t Type \t Options \t Description \t Persona
        tsv_5col = "VIN\ttext\t\tVehicle ID\tDistributor\nModel\tdrop_list\tT5,T7\tVehicle Model\tAgent\n".encode('utf-8')
        success, fields, msg = core.fields.parse_fields_file(tsv_5col, "test.tsv")
        self.assertTrue(success)
        self.assertEqual(len(fields), 2)
        self.assertEqual(fields[0]["title"], "VIN")
        self.assertEqual(fields[0]["description"], "Vehicle ID")
        self.assertEqual(fields[0]["persona"], "Distributor")
        self.assertEqual(fields[1]["title"], "Model")
        self.assertEqual(fields[1]["options"], ["T5", "T7"])
        self.assertEqual(fields[1]["description"], "Vehicle Model")
        self.assertEqual(fields[1]["persona"], "Agent")

        # 4-column with persona fallback
        tsv_4col_persona = "Status\ttext\t\tDistributor\n".encode('utf-8')
        success, fields2, _ = core.fields.parse_fields_file(tsv_4col_persona, "test.tsv")
        self.assertTrue(success)
        self.assertEqual(fields2[0]["persona"], "Distributor")
        self.assertEqual(fields2[0]["description"], "")

        # 4-column with description fallback
        tsv_4col_desc = "Remarks\ttext\t\tInternal notes for staff\n".encode('utf-8')
        success, fields3, _ = core.fields.parse_fields_file(tsv_4col_desc, "test.tsv")
        self.assertTrue(success)
        self.assertEqual(fields3[0]["description"], "Internal notes for staff")
        self.assertEqual(fields3[0]["persona"], "All")

        # Header-based CSV detection
        csv_header = "Field Name,Type,Description,Persona,Opt1,Opt2\nSeverity,drop_list,Ticket urgency,All,High,Low\n".encode('utf-8')
        success, fields4, _ = core.fields.parse_fields_file(csv_header, "test.csv")
        self.assertTrue(success)
        self.assertEqual(fields4[0]["title"], "Severity")
        self.assertEqual(fields4[0]["description"], "Ticket urgency")
        self.assertEqual(fields4[0]["options"], ["High", "Low"])

if __name__ == '__main__':
    unittest.main()


