import json
import tempfile
import unittest
from pathlib import Path

from cerberus.settings import Settings, vault_dir


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

    def test_new_settings_validate_and_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            custom = str((root / "memories").resolve())
            expected = Settings(mouse_gesture="back_button", hotkey="Ctrl+Shift+K",
                                shortcut_action="toggle", chat_level="chatty",
                                language="fa", roam=False, storage_dir=custom,
                                away_seconds=600, show_return_button=False)
            expected.save(root)
            self.assertEqual(Settings.load(root), expected)
            self.assertEqual(vault_dir(root), Path(custom))
            (root / "settings.json").write_text(json.dumps({
                "mouse_gesture": "telepathy", "hotkey": "C", "chat_level": "loud",
                "language": "klingon", "storage_dir": "relative/path", "away_seconds": 5,
            }), encoding="utf-8")
            bad = Settings.load(root)
            self.assertEqual((bad.mouse_gesture, bad.hotkey, bad.chat_level, bad.language),
                             ("left_right", "Ctrl+Alt+C", "normal", "auto"))
            self.assertEqual((bad.storage_dir, bad.away_seconds), ("", 180))
            self.assertEqual(vault_dir(root), root)

    def test_legacy_summon_chord_flag(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "settings.json").write_text(json.dumps({"summon_chord": False}),
                                                encoding="utf-8")
            self.assertEqual(Settings.load(root).mouse_gesture, "off")


if __name__ == "__main__":
    unittest.main()
