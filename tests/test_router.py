import unittest
import json
import io
from unittest.mock import patch
import core.router

class DummyHandler:
    def __init__(self, path, payload=None, headers=None):
        self.path = path
        self.headers = headers or {}
        body_bytes = json.dumps(payload or {}).encode('utf-8') if payload is not None else b""
        self.headers['Content-Length'] = str(len(body_bytes))
        self.rfile = io.BytesIO(body_bytes)
        self.wfile = io.BytesIO()
        self.response_code = 200
        self.response_headers = {}

    def send_response(self, code):
        self.response_code = code

    def send_header(self, key, value):
        self.response_headers[key] = value

    def end_headers(self):
        pass

class TestRouterIntegration(unittest.TestCase):
    def test_scan_voice_files_route(self):
        handler = DummyHandler('/api/scan-voice-files', {
            "dir_path": ".",
            "naming_mode": "exact"
        })
        core.router.dispatch_post(handler)
        self.assertIn(handler.response_code, [200, 400])
        response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        self.assertIn('success', response_data)

    def test_validate_ivr_route(self):
        handler = DummyHandler('/api/validate-ivr', {
            "workflow_content": "ivr_name: Test\nnodes:\n  - id: n1\n    type: start\n"
        })
        core.router.dispatch_post(handler)
        self.assertEqual(handler.response_code, 200)
        response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['data']['summary']['total_nodes'], 1)

    def test_fetch_custom_fields_invalid_auth_route(self):
        handler = DummyHandler('/api/fetch-custom-fields', {
            "auth_script": ""
        })
        core.router.dispatch_post(handler)
        self.assertEqual(handler.response_code, 400)
        response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        self.assertFalse(response_data['success'])

    def test_fetch_custom_fields_success_route(self):
        from unittest.mock import patch
        handler = DummyHandler('/api/fetch-custom-fields', {
            "auth_script": "dummy_script"
        })
        fake_data = {
            "count": 1,
            "stats": {"text": 1},
            "fields_json": {"ticketFields": [{"id": 1, "title": "Field 1"}]}
        }
        with patch("core.auth.parse_auth_string", return_value=({"base_url": "https://test.desk-platform.com"}, None)), \
             patch("core.fields.fetch_custom_fields", return_value=(True, fake_data, "Success")):
            core.router.dispatch_post(handler)
            self.assertEqual(handler.response_code, 200)
            response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
            self.assertTrue(response_data['success'])
            self.assertEqual(response_data['count'], 1)
            self.assertEqual(response_data['stats'], {"text": 1})
            self.assertIn("ticketFields", response_data['fields_json'])

    def test_create_custom_fields_invalid_auth_route(self):
        handler = DummyHandler('/api/create-custom-fields', {
            "auth_script": "",
            "fields": [{"title": "T1", "type": "text"}]
        })
        core.router.dispatch_post(handler)
        self.assertEqual(handler.response_code, 400)
        response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        self.assertFalse(response_data['success'])

    def test_create_custom_fields_empty_fields_route(self):
        handler = DummyHandler('/api/create-custom-fields', {
            "auth_script": "dummy",
            "fields": []
        })
        from unittest.mock import patch
        with patch("core.auth.parse_auth_string", return_value=({"base_url": "https://test.desk-platform.com"}, None)):
            core.router.dispatch_post(handler)
            self.assertEqual(handler.response_code, 400)
            response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
            self.assertFalse(response_data['success'])

    def test_create_custom_fields_stream_route(self):
        handler = DummyHandler('/api/create-custom-fields', {
            "auth_script": "dummy",
            "fields": [{"title": "T1", "type": "text"}]
        })
        from unittest.mock import patch
        fake_stream = [json.dumps({"status": "done", "total": 1, "success_count": 1}) + "\n"]
        with patch("core.auth.parse_auth_string", return_value=({"base_url": "https://test.desk-platform.com"}, None)), \
             patch("core.fields.create_custom_fields_stream", return_value=fake_stream):
            core.router.dispatch_post(handler)
            self.assertEqual(handler.response_code, 200)
            output = handler.wfile.getvalue().decode('utf-8')
            self.assertIn('"status": "done"', output)

    def test_migrate_fields_invalid_auth_route(self):
        handler = DummyHandler('/api/migrate-fields', {
            "auth_script": "invalid script",
            "raw_data": "{}"
        })
        core.router.dispatch_post(handler)
        self.assertEqual(handler.response_code, 400)
        response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        self.assertFalse(response_data['success'])

    def test_migrate_fields_stream_route(self):
        fake_stream = [json.dumps({"status": "progress", "message": "Field 1 done"}) + "\n", json.dumps({"status": "done"}) + "\n"]
        with patch("core.auth.parse_auth_string", return_value=({"base_url": "https://test.desk-platform.com"}, None)), \
             patch("core.fields.migrate_fields_stream", return_value=fake_stream):
            handler = DummyHandler('/api/migrate-fields', {
                "auth_script": "$session = ...",
                "raw_data": "{}"
            })
            core.router.dispatch_post(handler)
            self.assertEqual(handler.response_code, 200)
            output = handler.wfile.getvalue().decode('utf-8')
            self.assertIn('"status": "progress"', output)
            self.assertIn('"status": "done"', output)

    def test_create_agent_groups_invalid_auth_route(self):
        handler = DummyHandler('/api/create-agent-groups', {
            "auth_script": "",
            "group_names": ["Test Group"]
        })
        core.router.dispatch_post(handler)
        self.assertEqual(handler.response_code, 400)
        response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        self.assertFalse(response_data['success'])

    def test_assign_agents_invalid_auth_route(self):
        handler = DummyHandler('/api/assign-agents', {
            "auth_script": "",
            "groups_json": "[]",
            "agents_json": "[]",
            "mapping_csv": ""
        })
        core.router.dispatch_post(handler)
        self.assertEqual(handler.response_code, 400)
        response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        self.assertFalse(response_data['success'])

    def test_migrate_template_invalid_auth_route(self):
        handler = DummyHandler('/api/migrate-template', {
            "auth_a": "",
            "auth_b": "",
            "custom_fields_b": "[]"
        })
        core.router.dispatch_post(handler)
        self.assertEqual(handler.response_code, 400)
        response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        self.assertFalse(response_data['success'])

    def test_fetch_tenant_data_invalid_auth_route(self):
        handler = DummyHandler('/api/fetch-tenant-data', {
            "auth_script": ""
        })
        core.router.dispatch_post(handler)
        self.assertEqual(handler.response_code, 400)
        response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        self.assertFalse(response_data['success'])

    def test_fetch_tenant_data_success_route(self):
        from unittest.mock import patch
        handler = DummyHandler('/api/fetch-tenant-data', {
            "auth_script": "dummy_script"
        })
        with patch("core.auth.parse_auth_string", return_value=({"base_url": "https://test.desk-platform.com"}, None)), \
             patch("core.assign.fetch_groups_and_agents", return_value=(True, {"groups_json": {}, "agents_json": {}}, "OK")):
            core.router.dispatch_post(handler)
            self.assertEqual(handler.response_code, 200)
            response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
            self.assertTrue(response_data['success'])
            self.assertIn('groups_json', response_data)
            self.assertIn('agents_json', response_data)

    def test_stop_ivr_route(self):
        handler = DummyHandler('/api/stop-ivr', {})
        core.router.dispatch_post(handler)
        self.assertEqual(handler.response_code, 200)
        response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        self.assertTrue(response_data['success'])
        self.assertIn('stopped', response_data)

    def test_unknown_endpoint_returns_404(self):
        handler = DummyHandler('/api/non-existent-route', {})
        core.router.dispatch_post(handler)
        self.assertEqual(handler.response_code, 404)
        response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        self.assertFalse(response_data['success'])

    def test_dispatch_get_template(self):
        handler = DummyHandler('/api/download-custom-fields-template')
        handled = core.router.dispatch_get(handler)
        self.assertTrue(handled)
        self.assertEqual(handler.response_code, 200)
        self.assertIn('application/vnd.openxmlformats-officedocument', handler.response_headers.get('Content-Type', ''))

    def test_parse_custom_fields_file_route(self):
        import base64
        # Test with CSV bytes
        csv_bytes = "Title,Type,Opt1,Opt2\nCity,drop_list,Beijing,Shanghai\n".encode('utf-8')
        b64 = base64.b64encode(csv_bytes).decode('utf-8')
        handler = DummyHandler('/api/parse-custom-fields-file', {
            "filename": "test.csv",
            "content_base64": b64
        })
        core.router.dispatch_post(handler)
        self.assertEqual(handler.response_code, 200)
        response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        self.assertTrue(response_data['success'])
        self.assertEqual(len(response_data['fields']), 1)
        self.assertEqual(response_data['fields'][0]['title'], 'City')
        self.assertEqual(response_data['fields'][0]['type'], 'drop_list')
        self.assertEqual(response_data['fields'][0]['options'], ['Beijing', 'Shanghai'])

    def test_reload_all(self):
        import threading
        # Test reload_all when idle
        core.router.reload_all()

        # Test reload_all when an IVR build is active
        fake_evt = threading.Event()
        core.ivr.set_active_stop_event(fake_evt)
        try:
            core.router.reload_all()
        finally:
            core.ivr.set_active_stop_event(None)

    def test_validate_ivr_multi_canvas_route(self):
        multi_yaml = """
        ivr_name: "Multi-Language Test"
        canvases:
          - canvas_name: "Root Canvas"
            nodes:
              - id: start_1
                type: start
          - canvas_name: "Arabic Canvas"
            nodes:
              - id: start_2
                type: start
        """
        handler = DummyHandler('/api/validate-ivr', {
            "workflow_content": multi_yaml
        })
        core.router.dispatch_post(handler)
        self.assertEqual(handler.response_code, 200)
        data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        self.assertTrue(data['success'])
        self.assertTrue(data['data']['is_multi_canvas'])
        self.assertEqual(data['data']['canvases_count'], 2)

    def test_list_ivr_tabs_route_mocked(self):
        from unittest.mock import patch, MagicMock
        mock_tab = {"index": 0, "title": "IVR Editor", "url": "https://test.desk-platform.com/callcenter", "flow_name": "Main"}
        
        with patch('core.browser.connect_shared_browser') as mock_conn, \
             patch('core.browser.list_active_canvas_tabs') as mock_list:
            mock_conn.return_value = (MagicMock(), MagicMock(), "http://127.0.0.1:9225", False)
            mock_list.return_value = [mock_tab]
            
            handler = DummyHandler('/api/list-ivr-tabs', {"cdp_port": 9225})
            core.router.dispatch_post(handler)
            self.assertEqual(handler.response_code, 200)
            data = json.loads(handler.wfile.getvalue().decode('utf-8'))
            self.assertTrue(data['success'])
            self.assertEqual(data['count'], 1)
            self.assertEqual(data['tabs'][0]['title'], "IVR Editor")

    def test_fetch_agent_metadata_route(self):
        from unittest.mock import patch
        handler = DummyHandler('/api/fetch-agent-metadata', {
            "auth_script": "dummy_script"
        })
        with patch("core.auth.parse_auth_string", return_value=({"base_url": "https://test.desk-platform.com"}, None)), \
             patch("core.agents.fetch_agent_metadata", return_value=(True, {"roles": [{"id": 1, "name": "客服"}]}, "Success")):
            core.router.dispatch_post(handler)
            self.assertEqual(handler.response_code, 200)
            data = json.loads(handler.wfile.getvalue().decode('utf-8'))
            self.assertTrue(data['success'])
            self.assertEqual(len(data['data']['roles']), 1)

    def test_create_agents_route(self):
        from unittest.mock import patch
        handler = DummyHandler('/api/create-agents', {
            "auth_script": "dummy_script",
            "agents": [{"email": "test@test.com"}]
        })
        fake_chunks = [json.dumps({"status": "done", "success_count": 1}) + "\n"]
        with patch("core.auth.parse_auth_string", return_value=({"base_url": "https://test.desk-platform.com"}, None)), \
             patch("core.agents.create_agents_stream", return_value=iter(fake_chunks)):
            core.router.dispatch_post(handler)
            self.assertEqual(handler.response_code, 200)
            output = handler.wfile.getvalue().decode('utf-8')
    def test_parse_ticket_templates_route(self):
        handler = DummyHandler('/api/parse-ticket-templates', {
            "text": "Template: VIP Template\nVIN\ttrue\nCar Model\tfalse\n"
        })
        core.router.dispatch_post(handler)
        self.assertEqual(handler.response_code, 200)
        data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['total_fields'], 2)

    def test_batch_create_ticket_templates_route(self):
        from unittest.mock import patch
        handler = DummyHandler('/api/batch-create-ticket-templates', {
            "auth_script": "dummy_script",
            "templates": [{"name": "T1", "fields": [{"title": "F1", "required": True}]}]
        })
        fake_chunks = [json.dumps({"status": "done", "data": {"success": 1}}) + "\n"]
        with patch("core.auth.parse_auth_string", return_value=({"base_url": "https://test.desk-platform.com"}, None)), \
             patch("core.templates.create_ticket_templates_stream", return_value=iter(fake_chunks)):
            core.router.dispatch_post(handler)
            self.assertEqual(handler.response_code, 200)
            output = handler.wfile.getvalue().decode('utf-8')
            self.assertIn('"success": 1', output)

if __name__ == '__main__':
    unittest.main()
