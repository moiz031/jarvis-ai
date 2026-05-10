import unittest

from jarvis.config import Config


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.config = Config()

    def test_config_initialization(self):
        self.assertIsNotNone(self.config.WAKE_PHRASE)
        self.assertIn("jarvis", self.config.WAKE_PHRASE.lower())

    def test_paths_exist(self):
        # These paths are created in Config.__init__.
        self.assertTrue(self.config.APPS_JSON.parent.exists())
        self.assertTrue(self.config.MEMORY_DB.parent.exists())

    def test_kill_hotkey(self):
        self.assertEqual(self.config.KILL_HOTKEY, "ctrl+shift+k")


if __name__ == "__main__":
    unittest.main()
