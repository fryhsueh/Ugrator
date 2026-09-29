import unittest
import json
from unittest.mock import patch, MagicMock
import core.fields
from core.fields import fetch_custom_fields, create_custom_fields_stream
import core.router

class TestCustomerFields(unittest.TestCase):
    def test_fetch_customer_fields(self):
        auth_data = {"base_url": "https://tenant.desk-platform.com"}
        mock_response = {
            "status": 200,
            "data": {
                "custom_fields": [
                    {"id": 101, "title": "Customer VIP Level", "content_type": "droplist"},
                    {"id": 102, "title": "National ID", "content_type": "text"}
                ]
            }
        }
        with patch("core.fields.execute_request") as mock_exec:
            mock_exec.return_value = mock_response
            success, data, msg = fetch_custom_fields(auth_data, field_owner="Customer")

            self.assertTrue(success)
            self.assertEqual(data["count"], 2)
            self.assertEqual(data["stats"], {"droplist": 1, "text": 1})
            self.assertIn("customerFields", data["fields_json"])
            self.assertIn("custom_fields", data["fields_json"])
            self.assertIn("customer custom fields", msg.lower())

            # Verify URL called has field_owner=Customer
            call_args = mock_exec.call_args[0]
            self.assertIn("field_owner=Customer", call_args[0])

    def test_create_customer_fields_stream_payloads(self):
        auth_data = {"base_url": "https://tenant.desk-platform.com"}
        fields_to_create = [
            {"title": "Customer Address", "type": "text"},
            {"title": "Birth Date", "type": "date"},
            {"title": "Preferred Model", "type": "drop_list", "options": ["Model A", "Model B"]}
        ]

        captured_calls = []
        def mock_execute(url, method, payload, auth, **kwargs):
            captured_calls.append({"url": url, "method": method, "payload": payload})
            return {"status": 200, "data": {}}

        with patch("core.fields.execute_request", side_effect=mock_execute), patch("time.sleep", return_value=None):
            stream = create_custom_fields_stream(auth_data, fields_to_create, field_owner="Customer")
            events = [json.loads(line) for line in stream]

            self.assertEqual(events[0]["status"], "start")
            self.assertEqual(events[0]["field_owner"], "Customer")
            self.assertEqual(events[-1]["status"], "done")
            self.assertEqual(events[-1]["success_count"], 3)

            # Check 1st call: Text Field
            text_call = captured_calls[0]
            self.assertIn("/cs/ts/api/text_fields", text_call["url"])
            tf = text_call["payload"]["text_field"]
            self.assertEqual(tf["title"], "Customer Address")
            self.assertEqual(tf["field_owner"], "Customer")
            self.assertEqual(tf["agent_permission"], 2)
            self.assertEqual(tf["customer_permission"], 2)
            self.assertFalse(tf["is_encrypt"])

            # Check 2nd call: Date Field
            date_call = captured_calls[1]
            self.assertIn("/cs/ts/api/text_fields", date_call["url"])
            df = date_call["payload"]["text_field"]
            self.assertEqual(df["title"], "Birth Date")
            self.assertEqual(df["content_type"], "date")
            self.assertEqual(df["field_owner"], "Customer")
            self.assertEqual(df["agent_permission"], 2)
            self.assertEqual(df["customer_permission"], 2)

            # Check 3rd call: Dropdown Field
            drop_call = captured_calls[2]
            self.assertIn("/cs/ts/api/select_fields", drop_call["url"])
            sf = drop_call["payload"]["select_field"]
            self.assertEqual(sf["title"], "Preferred Model")
            self.assertEqual(sf["field_owner"], "Customer")
            self.assertEqual(sf["content_type"], "droplist")
            self.assertEqual(sf["agent_permission"], 2)
            self.assertEqual(sf["customer_permission"], 2)
            self.assertEqual(len(sf["select_options"]), 2)
            self.assertEqual(sf["select_options"][0]["title"], "Model A")
            self.assertEqual(sf["select_options"][1]["title"], "Model B")

    def test_router_customer_fields_endpoints(self):
        # Test handle_fetch_customer_fields
        handler = MagicMock()
        handler.headers = {"Content-Length": "100"}
        auth_script = 'Invoke-WebRequest -Uri "https://tenant.desk-platform.com" -Headers @{"X-CSRF-Token"="tok"}'
        handler.rfile.read.return_value = json.dumps({"auth_script": auth_script}).encode('utf-8')

        with patch("core.auth.parse_auth_string", return_value=({"base_url": "https://tenant.desk-platform.com"}, None)), \
             patch("core.fields.fetch_custom_fields", return_value=(True, {"count": 1, "stats": {}, "fields_json": {}}, "OK")) as mock_fetch, \
             patch("core.router.send_json") as mock_send_json:
            core.router.handle_fetch_customer_fields(handler)
            mock_fetch.assert_called_once()
            self.assertEqual(mock_fetch.call_args[1]["field_owner"], "Customer")
            mock_send_json.assert_called_once()
            self.assertEqual(mock_send_json.call_args[0][1], 200)

    def test_router_create_customer_fields_endpoint(self):
        handler = MagicMock()
        handler.headers = {"Content-Length": "150"}
        handler.wfile = MagicMock()
        req_body = {
            "auth_script": "dummy_script",
            "fields": [{"title": "Cust Field 1", "type": "text"}]
        }
        handler.rfile.read.return_value = json.dumps(req_body).encode('utf-8')

        with patch("core.auth.parse_auth_string", return_value=({"base_url": "https://tenant.desk-platform.com"}, None)), \
             patch("core.fields.create_custom_fields_stream", return_value=['{"status":"done"}\n']) as mock_stream:
            core.router.handle_create_customer_fields(handler)
            mock_stream.assert_called_once()
            self.assertEqual(mock_stream.call_args[1]["field_owner"], "Customer")
            handler.send_response.assert_called_with(200)

if __name__ == "__main__":
    unittest.main()

