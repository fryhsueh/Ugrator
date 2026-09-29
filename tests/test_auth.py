import unittest
from core.auth import parse_auth_string

class TestAuthModule(unittest.TestCase):
    def test_parse_auth_basic_post(self):
        script = """
        $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
        $session.Cookies.Add((New-Object System.Net.Cookie("HMACCOUNT", "MOCK_COOKIE_TOKEN_123", "/", ".desk-platform.com")))
        $session.Cookies.Add((New-Object System.Net.Cookie("ut_user_id", "%222%22", "/", ".desk-platform.com")))
        Invoke-WebRequest -UseBasicParsing -Uri "https://tenant-a.desk-platform.com/cs/ts/api/user_groups" `
        -Method "POST" `
        -WebSession $session `
        -Headers @{
          "Accept"="application/json, text/javascript, */*; q=0.01"
          "x-csrf-token"="token12345"
        } `
        -ContentType "application/json" `
        -Body "{`"user_group`":{`"name`":`"Test Group`"}}"
        """
        auth_data, err = parse_auth_string(script)
        self.assertIsNone(err)
        self.assertIsNotNone(auth_data)
        self.assertEqual(auth_data["base_url"], "https://tenant-a.desk-platform.com")
        self.assertEqual(auth_data["x_csrf_token"], "token12345")
        self.assertEqual(auth_data["cookies"]["HMACCOUNT"], "MOCK_COOKIE_TOKEN_123")
        self.assertEqual(auth_data["cookies"]["ut_user_id"], "%222%22")
        self.assertEqual(auth_data["body_json"], {"user_group": {"name": "Test Group"}})

    def test_parse_auth_utf8_template_put(self):
        script = r"""
        $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
        $session.Cookies.Add((New-Object System.Net.Cookie("_ga", "GA1.1.1000000000.1000000000", "/", ".desk-platform.com")))
        Invoke-WebRequest -UseBasicParsing -Uri "https://tenant-b.desk-platform.com/cs/ts/api/ticket_templates/2852" `
        -Method "PUT" `
        -WebSession $session `
        -Headers @{
          "Accept"="application/json"
        } `
        -ContentType "application/json" `
        -Body ([System.Text.Encoding]::UTF8.GetBytes("{`"ticket_template`":{`"id`":2852,`"name`":`"Default`"}}"))
        """
        auth_data, err = parse_auth_string(script)
        self.assertIsNone(err)
        self.assertIsNotNone(auth_data)
        self.assertEqual(auth_data["base_url"], "https://tenant-b.desk-platform.com")
        self.assertEqual(auth_data["template_id"], 2852)
        self.assertEqual(auth_data["body_json"], {"ticket_template": {"id": 2852, "name": "Default"}})

    def test_parse_auth_missing_uri(self):
        invalid_script = "$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession"
        auth_data, err = parse_auth_string(invalid_script)
        self.assertIsNone(auth_data)
        self.assertIn("Could not find base URL", err)

    def test_parse_auth_missing_cookies(self):
        script_no_cookies = 'Invoke-WebRequest -Uri "https://test.desk-platform.com/cs/ts/api/user_groups"'
        auth_data, err = parse_auth_string(script_no_cookies)
        self.assertIsNone(auth_data)
        self.assertIn("Could not find any cookies", err)

if __name__ == '__main__':
    unittest.main()
