import unittest
from unittest.mock import patch
from core.templates import migrate_template_data, migrate_template

class TestTemplatesModule(unittest.TestCase):
    def test_migrate_template_missing_id(self):
        auth_b = {"base_url": "https://test.desk-platform.com"}
        success, msg = migrate_template_data(auth_b, {}, {})
        self.assertFalse(success)
        self.assertIn("Could not find the target Template ID", msg)

    def test_migrate_template_success(self):
        auth_b = {
            "base_url": "https://test.desk-platform.com",
            "template_id": 999,
            "cookies": {},
            "x_csrf_token": "token"
        }
        payload_a = {
            "ticket_template": {
                "fields": [
                    {"title": "Priority", "id": 1, "field_id": 10, "name": "pri_old"}
                ]
            }
        }
        fields_b = {
            "ticketFields": [
                {"title": "Priority", "id": 2, "field_id": 20, "name": "pri_new"}
            ]
        }

        with patch("core.templates.execute_request", return_value={"status": 200}):
            success, msg = migrate_template(auth_b, payload_a, fields_b)
            self.assertTrue(success)
            self.assertIn("Successfully applied the configuration", msg)

    def test_parse_template_blocks_single_and_multi(self):
        from core.templates import parse_template_blocks
        raw_text = """
Template: Complaint Ticket
VIN	true
Car Model	false
*Dealer Code

Template: Maintenance Ticket
Plate Number	required
Mileage	optional
Service Type
"""
        success, tpls, msg = parse_template_blocks(raw_text)
        self.assertTrue(success)
        self.assertEqual(len(tpls), 2)
        
        # Template 1
        self.assertEqual(tpls[0]["name"], "Complaint Ticket")
        self.assertEqual(len(tpls[0]["fields"]), 3)
        self.assertEqual(tpls[0]["fields"][0]["title"], "VIN")
        self.assertTrue(tpls[0]["fields"][0]["required"])
        self.assertEqual(tpls[0]["fields"][1]["title"], "Car Model")
        self.assertFalse(tpls[0]["fields"][1]["required"])
        self.assertEqual(tpls[0]["fields"][2]["title"], "Dealer Code")
        self.assertTrue(tpls[0]["fields"][2]["required"])

        # Template 2
        self.assertEqual(tpls[1]["name"], "Maintenance Ticket")
        self.assertEqual(len(tpls[1]["fields"]), 3)
        self.assertEqual(tpls[1]["fields"][0]["title"], "Plate Number")
        self.assertTrue(tpls[1]["fields"][0]["required"])
        self.assertEqual(tpls[1]["fields"][1]["title"], "Mileage")
        self.assertFalse(tpls[1]["fields"][1]["required"])
        self.assertEqual(tpls[1]["fields"][2]["title"], "Service Type")
        self.assertFalse(tpls[1]["fields"][2]["required"])

    def test_parse_template_blocks_chinese_headers(self):
        from core.templates import parse_template_blocks
        raw_text = """
模板：售后工单
VIN码	必填
故障描述	选填
"""
        success, tpls, msg = parse_template_blocks(raw_text)
        self.assertTrue(success)
        self.assertEqual(len(tpls), 1)
        self.assertEqual(tpls[0]["name"], "售后工单")
        self.assertEqual(tpls[0]["fields"][0]["title"], "VIN码")
        self.assertTrue(tpls[0]["fields"][0]["required"])
        self.assertEqual(tpls[0]["fields"][1]["title"], "故障描述")
        self.assertFalse(tpls[0]["fields"][1]["required"])

    def test_validate_template_fields_strict_guard(self):
        from core.templates import validate_template_fields
        templates = [
            {
                "name": "T1",
                "fields": [
                    {"title": "ExistingField", "required": True},
                    {"title": "MissingField", "required": False}
                ]
            }
        ]
        tenant_fields = {
            "ticketFields": [
                {"title": "ExistingField", "id": 101, "name": "field_101"}
            ]
        }
        is_valid, matched, missing, duplicate_notices = validate_template_fields(templates, tenant_fields)
        self.assertFalse(is_valid)
        self.assertIn("ExistingField", matched)
        self.assertIn("T1", missing)
        self.assertIn("MissingField", missing["T1"])

    def test_parse_and_validate_field_ids_and_duplicates(self):
        from core.templates import parse_template_blocks, validate_template_fields

        raw_text = """
Template: Disambiguation Template
VIN (#202)\ttrue
#303\tfalse
field_404\ttrue
Description\trequired
"""
        success, tpls, msg = parse_template_blocks(raw_text)
        self.assertTrue(success)
        fields = tpls[0]["fields"]
        self.assertEqual(len(fields), 4)

        # 1. VIN (#202)
        self.assertEqual(fields[0]["title"], "VIN")
        self.assertEqual(fields[0]["target_id"], "202")
        self.assertTrue(fields[0]["required"])

        # 2. #303
        self.assertEqual(fields[1]["target_id"], "303")
        self.assertFalse(fields[1]["required"])

        # 3. field_404
        self.assertEqual(fields[2]["target_name"], "field_404")
        self.assertEqual(fields[2]["target_id"], "404")
        self.assertTrue(fields[2]["required"])

        # 4. Description (plain)
        self.assertEqual(fields[3]["title"], "Description")
        self.assertTrue(fields[3]["required"])

        # Tenant has duplicate "Description" fields (ID 501 and ID 502)
        tenant_fields = {
            "ticketFields": [
                {"id": 101, "name": "field_101", "title": "VIN"},
                {"id": 202, "name": "field_202", "title": "VIN"}, # The one targeted by VIN (#202)
                {"id": 303, "name": "field_303", "title": "Engine No"},
                {"id": 404, "name": "field_404", "title": "Transmission Code"},
                {"id": 501, "name": "field_501", "title": "Description"},
                {"id": 502, "name": "field_502", "title": "Description"}
            ]
        }

        is_valid, matched, missing, duplicates = validate_template_fields(tpls, tenant_fields)
        self.assertTrue(is_valid)
        self.assertEqual(len(missing), 0)

        # Field 0 should have matched ID 202 specifically
        self.assertEqual(fields[0]["resolved_id"], 202)
        self.assertEqual(fields[0]["display_title"], "VIN")

        # Field 1 should have matched ID 303
        self.assertEqual(fields[1]["resolved_id"], 303)
        self.assertEqual(fields[1]["display_title"], "Engine No")

        # Field 2 should have matched ID 404
        self.assertEqual(fields[2]["resolved_id"], 404)
        self.assertEqual(fields[2]["display_title"], "Transmission Code")

        # Field 3 (plain "Description") matches first (501) and flags duplicate notice
        self.assertEqual(fields[3]["resolved_id"], 501)
        self.assertIn("Description", duplicates)
        self.assertEqual(duplicates["Description"], ["501", "502"])

    def test_create_ticket_templates_stream_success(self):
        import json
        from core.templates import create_ticket_templates_stream

        auth_data = {"base_url": "https://tenant.desk-platform.com", "cookies": {}, "x_csrf_token": "csrf"}
        templates = [
            {
                "name": "VIP Template",
                "fields": [
                    {"title": "VIN", "target_id": "202", "required": True}
                ]
            }
        ]
        tenant_fields = {
            "ticketFields": [
                {"title": "VIN", "id": 101, "field_id": 101, "name": "field_101"},
                {"title": "VIN", "id": 202, "field_id": 202, "name": "field_202"}
            ]
        }

        captured_payloads = []
        def mock_execute(url, method, payload, auth):
            captured_payloads.append(payload)
            return {"status": 201, "data": {"ticket_template": {"id": 888}}}

        with patch("core.templates.execute_request", side_effect=mock_execute):
            chunks = list(create_ticket_templates_stream(auth_data, templates, tenant_fields_data=tenant_fields))
            msgs = [json.loads(c) for c in chunks]
            statuses = [m["status"] for m in msgs]
            self.assertIn("info", statuses)
            self.assertIn("progress", statuses)
            self.assertIn("done", statuses)
            done_msg = [m for m in msgs if m["status"] == "done"][0]
            self.assertEqual(done_msg["data"]["success"], 1)

            # Verify that the created template used ID 202, NOT ID 101
            created_fields = captured_payloads[0]["ticket_template"]["fields"]
            self.assertEqual(len(created_fields), 1)
            self.assertEqual(created_fields[0]["field_id"], 202)
            self.assertEqual(created_fields[0]["id"], "field_202")
            self.assertEqual(created_fields[0]["name"], "field_202")
            self.assertTrue(created_fields[0]["is_required"])

if __name__ == '__main__':
    unittest.main()
