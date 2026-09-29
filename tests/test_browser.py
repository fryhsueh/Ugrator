import unittest
from core.browser import is_cdp_port_active, discover_active_cdp_target, inject_auth_cookies

class DummyContext:
    def __init__(self):
        self.cookies_list = []

    def add_cookies(self, cookies):
        self.cookies_list.extend(cookies)

class TestBrowserModule(unittest.TestCase):
    def test_is_cdp_port_active_unopened_port(self):
        # A random unopened port should return False
        self.assertFalse(is_cdp_port_active(59999))

    def test_discover_active_cdp_target_with_url(self):
        url = "ws://127.0.0.1:9225/devtools/browser/xyz"
        res = discover_active_cdp_target(preferred_url=url)
        self.assertEqual(res, url)

    def test_inject_auth_cookies(self):
        dummy_context = DummyContext()
        auth_data = {
            "base_url": "https://tenant.s5.desk-platform.com/entry/manage",
            "cookies": {
                "_auth_session": "test_session_token_123",
                "remember_user_token": "remember_token_456"
            }
        }
        count = inject_auth_cookies(dummy_context, auth_data)
        self.assertEqual(count, 2)
        self.assertEqual(len(dummy_context.cookies_list), 2)
        self.assertEqual(dummy_context.cookies_list[0]["name"], "_auth_session")
        self.assertEqual(dummy_context.cookies_list[0]["domain"], "tenant.s5.desk-platform.com")

    def test_inject_auth_cookies_empty(self):
        dummy_context = DummyContext()
        count = inject_auth_cookies(dummy_context, None)
        self.assertEqual(count, 0)
        self.assertEqual(len(dummy_context.cookies_list), 0)

    def test_list_active_canvas_tabs_and_get_page(self):
        from core.browser import list_active_canvas_tabs, get_canvas_page_by_index

        class DummyPage:
            def __init__(self, url, title="IVR Flow"):
                self.url = url
                self._title = title
                self.frames = []
                self.brought_to_front = False

            def title(self):
                return self._title

            def bring_to_front(self):
                self.brought_to_front = True

        class DummyContextWithPages:
            def __init__(self, pages):
                self.pages = pages

        page1 = DummyPage("https://test.desk-platform.com/entry/manage/callcenter/ivr/flow-process?id=1", "Main IVR")
        page2 = DummyPage("https://google.com", "Google Search")
        page3 = DummyPage("https://test.desk-platform.com/entry/manage/callcenter/ivr/flow-process?id=2", "Arabic IVR")

        ctx = DummyContextWithPages([page1, page2, page3])
        tabs = list_active_canvas_tabs(ctx)
        self.assertEqual(len(tabs), 2)
        self.assertEqual(tabs[0]["index"], 0)
        self.assertEqual(tabs[0]["title"], "Main IVR")
        self.assertEqual(tabs[1]["index"], 2)
        self.assertEqual(tabs[1]["title"], "Arabic IVR")

        # Test get_canvas_page_by_index
        target = get_canvas_page_by_index(ctx, 2)
        self.assertIs(target, page3)
        self.assertTrue(page3.brought_to_front)

        # Invalid index returns None
        self.assertIsNone(get_canvas_page_by_index(ctx, 99))

if __name__ == '__main__':
    unittest.main()
