import unittest
import json
from unittest.mock import patch
from core.agents import (
    to_id_list,
    normalize_profile,
    fetch_agent_metadata,
    build_agent_payload,
    parse_agents_text,
    parse_agents_file,
    create_agents_stream
)

class TestAgentsModule(unittest.TestCase):
    def test_to_id_list(self):
        self.assertEqual(to_id_list("1694511"), [1694511])
        self.assertEqual(to_id_list("1694511, 1688021"), [1694511, 1688021])
        self.assertEqual(to_id_list([1694511, "1688021"]), [1694511, 1688021])
        self.assertEqual(to_id_list(1694511), [1694511])
        self.assertEqual(to_id_list("1694511.0"), [1694511])
        self.assertEqual(to_id_list(None), [])

    def test_normalize_profile(self):
        self.assertEqual(normalize_profile("ticket"), "ticket")
        self.assertEqual(normalize_profile("工单"), "ticket")
        self.assertEqual(normalize_profile("工单客服"), "ticket")
        self.assertEqual(normalize_profile("工单员工"), "ticket")
        self.assertEqual(normalize_profile("all"), "all")
        self.assertEqual(normalize_profile("全渠道"), "all")
        self.assertEqual(normalize_profile("callcenter"), "callcenter")
        self.assertEqual(normalize_profile("呼叫中心"), "callcenter")
        self.assertEqual(normalize_profile("im"), "im")
        self.assertEqual(normalize_profile("在线客服"), "im")
        self.assertEqual(normalize_profile("", default="all"), "all")
        self.assertEqual(normalize_profile(None, default="ticket"), "ticket")

    def test_fetch_agent_metadata(self):
        auth_data = {
            "base_url": "https://test.desk-platform.com",
            "cookies": {},
            "x_csrf_token": "token123"
        }

        def mock_exec(url, method, payload, auth):
            if "agent_roles" in url:
                return {"status": 200, "data": {"agent_roles": [{"id": 1694511, "name": "客服"}]}}
            elif "user_groups" in url:
                return {"status": 200, "data": {"user_groups": [{"id": 1688021, "name": "默认组"}]}}
            elif "departments" in url:
                return {"status": 200, "data": {"departments": [{"id": 1668261, "name": "HQ", "is_default": True}]}}
            return {"status": 404}

        with patch("core.agents.execute_request", side_effect=mock_exec), patch("time.sleep", return_value=None):
            success, data, msg = fetch_agent_metadata(auth_data)
            self.assertTrue(success)
            self.assertEqual(len(data["roles"]), 1)
            self.assertEqual(data["roles"][0]["name"], "客服")
            self.assertEqual(data["default_group_id"], 1688021)
            self.assertEqual(data["default_dept_id"], 1668261)

    def test_build_agent_payload(self):
        agent_item = {
            "email": "agent1@example.com",
            "profile": "all",
            "agent_role_ids": [1694511]
        }
        defaults = {
            "password": "Pass2026",
            "profile": "all",
            "user_group_ids": [1688021],
            "department_ids": [1668261]
        }
        payload = build_agent_payload(agent_item, defaults)
        agent = payload["agent"]
        self.assertEqual(agent["email"], "agent1@example.com")
        self.assertEqual(agent["profile"], "all")
        self.assertEqual(agent["password"], "Pass2026")
        self.assertEqual(agent["agent_role_ids"], [1694511])
        self.assertEqual(agent["user_group_ids"], [1688021])
        self.assertEqual(agent["department_ids"], [1668261])

    def test_build_agent_payload_ticket(self):
        agent_item = {
            "email": "ticket.agent@example.com",
            "name": "Ticket Master",
            "profile": "工单"
        }
        payload = build_agent_payload(agent_item)
        agent = payload["agent"]
        self.assertEqual(agent["email"], "ticket.agent@example.com")
        self.assertEqual(agent["profile"], "ticket")
        self.assertEqual(agent["name"], "Ticket Master")
        self.assertEqual(agent["nick_name"], "Ticket Master")
        self.assertEqual(agent["im_ability_value"], "10")

    def test_build_agent_payload_with_nickname(self):
        # 1. Nickname only
        agent_item1 = {
            "email": "nick@test.com",
            "nick_name": "QuickNick"
        }
        payload1 = build_agent_payload(agent_item1)
        self.assertEqual(payload1["agent"]["nick_name"], "QuickNick")
        self.assertEqual(payload1["agent"]["name"], "QuickNick")

        # 2. Both Name and Nickname
        agent_item2 = {
            "email": "both@test.com",
            "name": "Alexander Real",
            "nick_name": "Alex"
        }
        payload2 = build_agent_payload(agent_item2)
        self.assertEqual(payload2["agent"]["name"], "Alexander Real")
        self.assertEqual(payload2["agent"]["nick_name"], "Alex")

        # 3. Neither Name nor Nickname
        agent_item3 = {
            "email": "plain@test.com"
        }
        payload3 = build_agent_payload(agent_item3)
        self.assertNotIn("name", payload3["agent"])
        self.assertNotIn("nick_name", payload3["agent"])

    def test_parse_agents_text(self):
        text = """
        agent1@example.com, Agent One
        agent2@example.com	Agent Two
        agent3@example.com, Agent Three, Pass2026, 1694511, ticket
        agent4@example.com, Agent Four, 工单
        """
        agents = parse_agents_text(text, default_profile="all", default_role_ids=[1694511])
        self.assertEqual(len(agents), 4)
        self.assertEqual(agents[0]["email"], "agent1@example.com")
        self.assertEqual(agents[0]["nick_name"], "Agent One")
        self.assertEqual(agents[0]["profile"], "all")

        self.assertEqual(agents[1]["email"], "agent2@example.com")
        self.assertEqual(agents[1]["profile"], "all")

        self.assertEqual(agents[2]["email"], "agent3@example.com")
        self.assertEqual(agents[2]["profile"], "ticket")
        self.assertEqual(agents[2]["password"], "Pass2026")
        self.assertEqual(agents[2]["agent_role_ids"], [1694511])

        self.assertEqual(agents[3]["email"], "agent4@example.com")
        self.assertEqual(agents[3]["profile"], "ticket")

    def test_parse_agents_file_csv(self):
        csv_data = """姓名,昵称,邮箱（登录账号）,初始密码,员工类型,角色
张三,小张,zhangsan@example.com,Pass2026,工单,1694511
李四,小李,lisi@example.com,Pass2026,在线客服,1694512
""".encode('utf-8')
        success, agents, msg = parse_agents_file(csv_data, "test.csv")
        self.assertTrue(success)
        self.assertEqual(len(agents), 2)
        self.assertEqual(agents[0]["email"], "zhangsan@example.com")
        self.assertEqual(agents[0]["name"], "张三")
        self.assertEqual(agents[0]["nick_name"], "小张")
        self.assertEqual(agents[0]["profile"], "ticket")
        self.assertEqual(agents[0]["agent_role_ids"], [1694511])

        self.assertEqual(agents[1]["email"], "lisi@example.com")
        self.assertEqual(agents[1]["profile"], "im")

    def test_create_agents_stream(self):
        auth_data = {
            "base_url": "https://test.desk-platform.com",
            "cookies": {}
        }
        agents = [{"email": "a1@test.com", "nick_name": "Agent1", "profile": "ticket"}, {"email": "a2@test.com"}]
        mock_responses = [
            {"status": 200, "data": {"code": 1000}},
            {"status": 200, "data": {"code": 1000}}
        ]
        with patch("core.agents.execute_request", side_effect=mock_responses), patch("time.sleep", return_value=None):
            chunks = list(create_agents_stream(auth_data, agents))
            done = json.loads(chunks[-1])
            self.assertEqual(done["status"], "done")
            self.assertEqual(done["success_count"], 2)
            log_messages = [json.loads(c)["message"] for c in chunks if json.loads(c).get("status") == "log"]
            self.assertTrue(any("Nick: Agent1" in m for m in log_messages))
            self.assertTrue(any("Type: ticket" in m for m in log_messages))

if __name__ == '__main__':
    unittest.main()
