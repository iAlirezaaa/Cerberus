import json
import tempfile
import unittest
from pathlib import Path

from cerberus.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_default_is_private(self):
        with tempfile.TemporaryDirectory() as folder:
            current = Settings.load(Path(folder))
            self.assertFalse(current.clipboard_capture)
            self.assertFalse(current.reduced_motion)
            self.assertTrue(current.show_pet)

    def test_saved_values_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            expected = Settings(clipboard_capture=True, show_pet=False, reduced_motion=True)
            expected.save(root)
            self.assertEqual(Settings.load(root), expected)

    def test_bad_json_uses_safe_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "settings.json").write_text("{bad json", encoding="utf-8")
            self.assertFalse(Settings.load(root).clipboard_capture)
            (root / "settings.json").write_text(
                json.dumps({"clipboard_capture": "true", "show_pet": False}), encoding="utf-8")
            result = Settings.load(root)
            self.assertFalse(result.clipboard_capture)
            self.assertFalse(result.show_pet)


if __name__ == "__main__":
    unittest.main()
