import unittest
from core.assign import extract_mapping

class TestAssignModule(unittest.TestCase):
    def test_extract_mapping_groups(self):
        sample_groups = {
            "user_groups": [
                {"id": 101, "name": "Sales Team"},
                {"id": 102, "name": "Support Team"}
            ]
        }
        mapping = {}
        extract_mapping(sample_groups, "name", "id", mapping)
        self.assertEqual(mapping["Sales Team"], 101)
        self.assertEqual(mapping["Support Team"], 102)

    def test_extract_mapping_agents(self):
        sample_agents = {
            "agents": [
                {"id": 501, "email": "Agent1@test.com", "name": "Agent One"},
                {"id": 502, "email": "Agent2@TEST.com", "name": "Agent Two"}
            ]
        }
        mapping = {}
        extract_mapping(sample_agents, "email", "id", mapping)
        # Should be lowercase email keys
        self.assertEqual(mapping["agent1@test.com"], 501)
        self.assertEqual(mapping["agent2@test.com"], 502)

    def test_fetch_groups_and_agents_success(self):
        from unittest.mock import patch
        from core.assign import fetch_groups_and_agents

        auth_data = {
            "base_url": "https://test.desk-platform.com",
            "cookies": {},
            "x_csrf_token": "token123"
        }

        def mock_exec(url, method, payload, auth):
            if "user_groups" in url:
                return {"status": 200, "data": {"user_groups": [{"id": 1, "name": "Team A"}]}}
            elif "agents" in url:
                return {"status": 200, "data": {"agents": [{"id": 10, "email": "a@test.com"}]}}
            return {"status": 404}

        with patch("core.assign.execute_request", side_effect=mock_exec), patch("time.sleep", return_value=None):
            success, data, msg = fetch_groups_and_agents(auth_data)
            self.assertTrue(success)
            self.assertIn("user_groups", data["groups_json"])
            self.assertIn("agents", data["agents_json"])
            self.assertIn("Fetched 1 groups and 1 agents", msg)

    def test_fetch_groups_and_agents_missing_base_url(self):
        from core.assign import fetch_groups_and_agents
        success, data, msg = fetch_groups_and_agents({})
        self.assertFalse(success)
        self.assertIn("Missing base URL", msg)

if __name__ == '__main__':
    unittest.main()
