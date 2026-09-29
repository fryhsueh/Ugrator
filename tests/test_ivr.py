import unittest
from core.ivr import parse_ivr_workflow, calculate_dag_layout

SAMPLE_VALID_YAML = """
ivr_name: "Customer Service IVR"
nodes:
  - id: start_node
    type: start
    title: "Start"
    routes:
      default: welcome_node

  - id: welcome_node
    type: voice_playback
    title: "Welcome Greeting"
    audio: "Welcome_MSG_EN"
    routes:
      default: lang_menu

  - id: lang_menu
    type: collect_input
    title: "Language Menu"
    audio: "MainMenu_MSG"
    config:
      timeout_seconds: 5
      max_retries: 3
    routes:
      keys:
        "1": sales_queue
        "2": service_queue
      timeout: no_input_node
      invalid: invalid_option_node

  - id: sales_queue
    type: enter_queue
    title: "Sales Queue"
    config:
      group_name: "Sales Team"
    routes:
      default: hangup_node

  - id: service_queue
    type: enter_queue
    title: "Service Queue"
    config:
      group_name: "Service Team"
    routes:
      default: hangup_node

  - id: no_input_node
    type: voice_playback
    title: "No Input Notice"
    audio: "NoInput_1_MSG"
    routes:
      default: lang_menu

  - id: invalid_option_node
    type: voice_playback
    title: "Invalid Option Notice"
    audio: "InvalidOption_MSG"
    routes:
      default: lang_menu

  - id: hangup_node
    type: hang_up
    title: "End Call"
"""

class TestIVRModule(unittest.TestCase):
    def test_parse_valid_workflow(self):
        res = parse_ivr_workflow(SAMPLE_VALID_YAML)
        self.assertTrue(res["valid"])
        self.assertEqual(res["ivr_name"], "Customer Service IVR")
        self.assertEqual(len(res["nodes"]), 8)
        self.assertIn("Welcome_MSG_EN", res["referenced_voices"])
        self.assertIn("MainMenu_MSG", res["referenced_voices"])
        self.assertIn("NoInput_1_MSG", res["referenced_voices"])
        self.assertIn("InvalidOption_MSG", res["referenced_voices"])
        self.assertEqual(res["summary"]["total_nodes"], 8)
        self.assertEqual(res["summary"]["type_breakdown"]["voice_playback"], 3)
        self.assertEqual(res["summary"]["type_breakdown"]["enter_queue"], 2)

    def test_parse_empty_workflow(self):
        res = parse_ivr_workflow("")
        self.assertFalse(res["valid"])
        self.assertIn("empty", res["error"])

    def test_parse_invalid_target_node(self):
        bad_yaml = """
        nodes:
          - id: start_node
            type: start
            routes:
              default: non_existent_node
        """
        res = parse_ivr_workflow(bad_yaml)
        self.assertFalse(res["valid"])
        self.assertIn("unknown node 'non_existent_node'", res["error"])

    def test_parse_duplicate_node_id(self):
        bad_yaml = """
        nodes:
          - id: node_1
            type: start
          - id: node_1
            type: hang_up
        """
        res = parse_ivr_workflow(bad_yaml)
        self.assertFalse(res["valid"])
        self.assertIn("Duplicate node id", res["error"])

    def test_calculate_dag_layout_coordinates(self):
        res = parse_ivr_workflow(SAMPLE_VALID_YAML)
        self.assertTrue(res["valid"])
        nodes = res["nodes"]
        
        # Start node must be at X=80
        start = next(n for n in nodes if n["id"] == "start_node")
        self.assertEqual(start["x"], 80)
        
        # Welcome node is depth 1 -> X = 80 + 190 = 270
        welcome = next(n for n in nodes if n["id"] == "welcome_node")
        self.assertEqual(welcome["x"], 270)

        # lang_menu is depth 2 -> X = 80 + 2*190 = 460
        menu = next(n for n in nodes if n["id"] == "lang_menu")
        self.assertEqual(menu["x"], 460)

        # Sales & Service queue should have higher X than lang_menu
        sales = next(n for n in nodes if n["id"] == "sales_queue")
        self.assertGreater(sales["x"], menu["x"])

    def test_parse_info_judgment_rules_and_dag(self):
        multilang_yaml = """
        ivr_name: "Dual Language IVR"
        nodes:
          - id: start_node
            type: start
            routes:
              default: lang_judgment
          - id: lang_judgment
            type: info_judgment
            title: "Language Judgment"
            rules:
              - name: "Arabic"
                variable: "User Input"
                operator: "Equal"
                value: "1"
                target: ar_menu
              - name: "English"
                variable: "User Input"
                operator: "Equal"
                value: "2"
                target: en_menu
            routes:
              default: en_menu
          - id: ar_menu
            type: collect_input
            title: "Arabic Menu"
          - id: en_menu
            type: collect_input
            title: "English Menu"
        """
        res = parse_ivr_workflow(multilang_yaml)
        self.assertTrue(res["valid"])
        self.assertEqual(len(res["nodes"]), 4)
        
        # Test DAG level calculation with rule targets
        start = next(n for n in res["nodes"] if n["id"] == "start_node")
        judge = next(n for n in res["nodes"] if n["id"] == "lang_judgment")
        ar = next(n for n in res["nodes"] if n["id"] == "ar_menu")
        en = next(n for n in res["nodes"] if n["id"] == "en_menu")
        
        self.assertEqual(start["x"], 80)
        self.assertEqual(judge["x"], 270)
        self.assertEqual(ar["x"], 460)
        self.assertEqual(en["x"], 460)
        # Verify dual branches are separated vertically into distinct lanes
        self.assertGreater(ar["y"], 1000)
        self.assertLess(en["y"], 500)
        self.assertGreaterEqual(abs(ar["y"] - en["y"]), 500)

    def test_branch_aware_layout_no_overlap(self):
        with open("workflows/sample_customer_service_ivr.yaml", "r", encoding="utf-8") as f:
            yaml_content = f.read()
        res = parse_ivr_workflow(yaml_content)
        self.assertTrue(res["valid"])
        nodes = res["nodes"]
        self.assertEqual(len(nodes), 50)
        # Verify that no two nodes have identical (x, y) coordinates
        coords = [(n["x"], n["y"]) for n in nodes]
        self.assertEqual(len(coords), len(set(coords)), "Found overlapping nodes with identical (x, y) coordinates")

    def test_request_ivr_stop_mechanism(self):
        from core.ivr import request_ivr_stop, build_ivr_stream
        import threading
        import json

        # When no build is active, request_ivr_stop returns False
        self.assertFalse(request_ivr_stop())

        # Test pre-set stop_event halts build_ivr_stream gracefully
        stop_event = threading.Event()
        stop_event.set()

        stream = build_ivr_stream(SAMPLE_VALID_YAML, stop_event=stop_event)
        chunks = list(stream)
        messages = [json.loads(c).get("message", "") for c in chunks if c.strip()]
        
        # Verify stopped log is present and execution terminated early
        self.assertTrue(any("stopped by user" in m.lower() for m in messages))

    def test_request_ivr_stop_survives_reload(self):
        import importlib
        import core.ivr
        import threading

        evt = threading.Event()
        core.ivr.set_active_stop_event(evt)
        self.assertFalse(evt.is_set())

        # Reload core.ivr dynamically
        importlib.reload(core.ivr)

        # Call request_ivr_stop() from newly reloaded module
        res = core.ivr.request_ivr_stop()
        self.assertTrue(res)
        self.assertTrue(evt.is_set())

        # Cleanup
        core.ivr.set_active_stop_event(None)

    def test_multi_canvas_workflow_parsing(self):
        multi_yaml = """
        ivr_name: "Multi-Language Modular IVR"
        canvases:
          - canvas_name: "Root - Greeting & Language"
            nodes:
              - id: root_start
                type: start
                routes:
                  default: root_greeting
              - id: root_greeting
                type: voice_playback
                audio: "Root_Welcome"

          - canvas_name: "Arabic Sub-flow"
            nodes:
              - id: ar_start
                type: start
                routes:
                  default: ar_menu
              - id: ar_menu
                type: collect_input
                audio: "AR_Menu"

          - canvas_name: "English Sub-flow"
            nodes:
              - id: en_start
                type: start
                routes:
                  default: en_menu
              - id: en_menu
                type: collect_input
                audio: "EN_Menu"
        """
        res = parse_ivr_workflow(multi_yaml)
        self.assertTrue(res["valid"])
        self.assertTrue(res["is_multi_canvas"])
        self.assertEqual(res["canvases_count"], 3)
        self.assertEqual(len(res["canvases"]), 3)
        self.assertEqual(res["summary"]["total_nodes"], 6)
        self.assertEqual(len(res["referenced_voices"]), 3)
        self.assertIn("Root_Welcome", res["referenced_voices"])
        self.assertIn("AR_Menu", res["referenced_voices"])
        self.assertIn("EN_Menu", res["referenced_voices"])

        # Verify each canvas has independent DAG coordinate assignment starting at X=80
        for c in res["canvases"]:
            start_node = c["nodes"][0]
            self.assertEqual(start_node["type"], "start")
            self.assertEqual(start_node["x"], 80)

    def test_multi_canvas_strict_start_node_enforcement(self):
        # Missing start node on canvas 2
        bad_yaml = """
        ivr_name: "Missing Start Node IVR"
        canvases:
          - canvas_name: "Canvas 1"
            nodes:
              - id: start_1
                type: start
          - canvas_name: "Canvas 2"
            nodes:
              - id: greeting_2
                type: voice_playback
        """
        res = parse_ivr_workflow(bad_yaml)
        self.assertFalse(res["valid"])
        self.assertIn("must begin with a 'start' node as its entry point", res["error"])
        self.assertIn("Canvas 2", res["error"])

    def test_multi_canvas_duplicate_start_node_enforcement(self):
        # Multiple start nodes on one canvas
        bad_yaml = """
        canvases:
          - canvas_name: "Canvas 1"
            nodes:
              - id: start_1
                type: start
              - id: start_2
                type: start
        """
        res = parse_ivr_workflow(bad_yaml)
        self.assertFalse(res["valid"])
        self.assertIn("cannot contain more than one 'start' node", res["error"])

    def test_multilang_multicanvas_template_validation(self):
        # Extract multilang_multicanvas template from frontend/app.js
        import re, os
        app_js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "app.js"))
        with open(app_js_path, "r", encoding="utf-8") as f:
            app_js = f.read()
        match = re.search(r'multilang_multicanvas:\s*`([^`]+)`', app_js)
        self.assertIsNotNone(match, "multilang_multicanvas template not found in frontend/app.js")
        template_yaml = match.group(1)

        res = parse_ivr_workflow(template_yaml)
        self.assertTrue(res["valid"], f"Template failed validation: {res.get('error')}")
        self.assertTrue(res["is_multi_canvas"])
        self.assertEqual(res["canvases_count"], 3)

        # Check each canvas has an info_judgment branch node
        for c in res["canvases"]:
            c_name = c["canvas_name"]
            info_nodes = [n for n in c["nodes"] if n["type"] == "info_judgment"]
            self.assertEqual(len(info_nodes), 1, f"Canvas '{c_name}' should have exactly 1 info_judgment branch node")
            judg_node = info_nodes[0]
            self.assertGreaterEqual(len(judg_node.get("rules", [])), 2, f"Info judgment in '{c_name}' must have at least 2 rules")
            
            # Check collect_input routes to info_judgment
            collect_nodes = [n for n in c["nodes"] if n["type"] == "collect_input"]
            self.assertEqual(len(collect_nodes), 1, f"Canvas '{c_name}' should have 1 collect_input node")
            c_input = collect_nodes[0]
            self.assertEqual(c_input["routes"].get("default"), judg_node["id"])

if __name__ == '__main__':
    unittest.main()

