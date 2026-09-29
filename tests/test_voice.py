import os
import tempfile
import unittest
from core.voice import generate_voice_name, scan_voice_files, normalize_target_voice_url

class TestVoiceModule(unittest.TestCase):
    def test_normalize_target_voice_url(self):
        # 1. Arbitrary sub-path e.g. agent-roles
        url, dom = normalize_target_voice_url("https://sample-tenant.desk-platform.com/entry/manage/agent-roles")
        self.assertEqual(dom, "sample-tenant.desk-platform.com")
        self.assertEqual(url, "https://sample-tenant.desk-platform.com/entry/manage/callcenter/voice-list")

        # 2. Callcenter root
        url, dom = normalize_target_voice_url("https://sample-tenant.desk-platform.com/entry/manage/callcenter")
        self.assertEqual(dom, "sample-tenant.desk-platform.com")
        self.assertEqual(url, "https://sample-tenant.desk-platform.com/entry/manage/callcenter/voice-list")

        # 3. Base domain only
        url, dom = normalize_target_voice_url("https://sample-tenant.desk-platform.com")
        self.assertEqual(dom, "sample-tenant.desk-platform.com")
        self.assertEqual(url, "https://sample-tenant.desk-platform.com/entry/manage/callcenter/voice-list")

        # 4. Domain without protocol
        url, dom = normalize_target_voice_url("sample-tenant.desk-platform.com")
        self.assertEqual(dom, "sample-tenant.desk-platform.com")
        self.assertEqual(url, "https://sample-tenant.desk-platform.com/entry/manage/callcenter/voice-list")

        # 5. Direct voice list link
        url, dom = normalize_target_voice_url("https://tenant-a.s5.desk-platform.com/entry/manage/callcenter/voice-list")
        self.assertEqual(dom, "tenant-a.s5.desk-platform.com")
        self.assertEqual(url, "https://tenant-a.s5.desk-platform.com/entry/manage/callcenter/voice-list")

        # 6. Auth data fallback
        url, dom = normalize_target_voice_url(None, auth_data={"base_url": "https://tenant.s5.desk-platform.com"})
        self.assertEqual(dom, "tenant.s5.desk-platform.com")
        self.assertEqual(url, "https://tenant.s5.desk-platform.com/entry/manage/callcenter/voice-list")

    def test_generate_voice_name_exact(self):
        name = generate_voice_name("welcome.mp3", "IVR_Folder", naming_mode="exact")
        self.assertEqual(name, "welcome")

    def test_generate_voice_name_folder_suffix(self):
        name = generate_voice_name("welcome.wav", "IVR_Folder", naming_mode="folder_suffix")
        self.assertEqual(name, "welcome_IVR_Folder")

    def test_generate_voice_name_prefix(self):
        name = generate_voice_name("agent_busy.ogg", "Prompts", naming_mode="prefix", prefix="DEMO_")
        self.assertEqual(name, "DEMO_agent_busy")

    def test_generate_voice_name_suffix(self):
        name = generate_voice_name("agent_busy.m4a", "Prompts", naming_mode="suffix", suffix="_BR")
        self.assertEqual(name, "agent_busy_BR")

    def test_generate_voice_name_custom_pattern(self):
        name = generate_voice_name(
            "greeting.wav", "Sales",
            naming_mode="custom",
            prefix="SAMPLE_",
            suffix="_V1",
            pattern="{prefix}{folder}_{file}{suffix}"
        )
        self.assertEqual(name, "SAMPLE_Sales_greeting_V1")

    def test_scan_voice_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subfolder = os.path.join(tmpdir, "SubIVR")
            os.makedirs(subfolder)
            
            # Create sample files
            f1 = os.path.join(tmpdir, "intro.mp3")
            f2 = os.path.join(subfolder, "queue.wav")
            f3 = os.path.join(tmpdir, "ignore.txt") # Non-audio

            with open(f1, "wb") as f:
                f.write(b"RIFF" + b"\x00" * 1024)
            with open(f2, "wb") as f:
                f.write(b"RIFF" + b"\x00" * 2048)
            with open(f3, "w") as f:
                f.write("test text")

            success, files = scan_voice_files(tmpdir, naming_mode="folder_suffix")
            self.assertTrue(success)
            self.assertEqual(len(files), 2)
            
            filenames = [f["filename"] for f in files]
            self.assertIn("intro.mp3", filenames)
            self.assertIn("queue.wav", filenames)
            self.assertNotIn("ignore.txt", filenames)

            for item in files:
                if item["filename"] == "queue.wav":
                    self.assertEqual(item["voice_name"], "queue_SubIVR")

    def test_parse_voice_tts_text_tsv_and_csv(self):
        from core.voice import parse_voice_tts_text
        tsv_data = "welcome\tWelcome to customer service.\t小夏\nqueue_wait\tAll agents are busy, please wait.\n"
        success, items, msg = parse_voice_tts_text(tsv_data, default_timbre="小夏")
        self.assertTrue(success)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["name"], "welcome")
        self.assertEqual(items[0]["content"], "Welcome to customer service.")
        self.assertEqual(items[0]["timbre"], "小夏")
        self.assertEqual(items[1]["name"], "queue_wait")
        self.assertEqual(items[1]["content"], "All agents are busy, please wait.")
        self.assertEqual(items[1]["timbre"], "小夏")

        # CSV format with quotes and commas
        csv_data = '"greeting","Hello, thank you for calling, how may I help?","小美"\n'
        success, items2, _ = parse_voice_tts_text(csv_data)
        self.assertTrue(success)
        self.assertEqual(len(items2), 1)
        self.assertEqual(items2[0]["name"], "greeting")
        self.assertEqual(items2[0]["content"], "Hello, thank you for calling, how may I help?")
        self.assertEqual(items2[0]["timbre"], "小美")

    def test_parse_voice_tts_text_header_skipping(self):
        from core.voice import parse_voice_tts_text
        tsv_with_header = "Voice Name\tPrompt Content\tTimbre\nprompt1\tThank you for calling.\t小夏\n"
        success, items, _ = parse_voice_tts_text(tsv_with_header)
        self.assertTrue(success)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "prompt1")

    def test_parse_voice_tts_text_empty(self):
        from core.voice import parse_voice_tts_text
        success, items, msg = parse_voice_tts_text("")
        self.assertFalse(success)
        self.assertEqual(len(items), 0)

    def test_timbre_mapping_cn_to_en(self):
        from core.voice import TIMBRE_MAP_CN_TO_EN
        self.assertEqual(TIMBRE_MAP_CN_TO_EN.get("小夏"), "Little Summer")
        self.assertEqual(TIMBRE_MAP_CN_TO_EN.get("小雪"), "Light Snow")
        self.assertEqual(TIMBRE_MAP_CN_TO_EN.get("小树"), "Little Tree")
        self.assertEqual(TIMBRE_MAP_CN_TO_EN.get("NonExistent", "NonExistent"), "NonExistent")

if __name__ == '__main__':
    unittest.main()
