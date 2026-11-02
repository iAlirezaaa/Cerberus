import json
import tempfile
import unittest
from pathlib import Path

from cerberus.vault import CaptureError, MAX_FILE_BYTES, MAX_TEXT_BYTES, Vault


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.vault = Vault(self.root / "data")

    def tearDown(self):
        self.vault.close()
        self.temp.cleanup()

    def test_text_round_trip_and_unicode_search(self):
        note = self.vault.add_text("برنامهٔ انیمیشن یروما", title="Production note")
        self.assertEqual(self.vault.get(note["id"])["content"], "برنامهٔ انیمیشن یروما")
        self.assertEqual(len(self.vault.search("Production")), 1)
        self.assertEqual(len(self.vault.search("انیمیشن")), 1)

    def test_duplicate_text_returns_same_item(self):
        a = self.vault.add_text("Keep this")
        b = self.vault.add_text("Keep this", title="Different title")
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(len(self.vault.list()), 1)

    def test_url_detection_and_validation(self):
        item = self.vault.capture_text("https://example.org/notes")
        self.assertEqual(item["kind"], "url")
        with self.assertRaises(CaptureError):
            self.vault.add_url("file:///etc/passwd")
        self.assertEqual(self.vault.capture_text("hello world")["kind"], "text")

    def test_file_is_copied_and_delete_does_not_touch_source(self):
        src = self.root / "example.txt"
        src.write_text("Test file data", encoding="utf-8")
        a = self.vault.add_file(src)
        saved = Path(a["stored_path"])
        self.assertTrue(saved.is_file())
        self.assertNotEqual(saved.resolve(), src.resolve())
        self.assertEqual(saved.read_text(encoding="utf-8"), "Test file data")
        b = self.vault.add_file(src)
        self.assertEqual(a["id"], b["id"])
        self.assertTrue(self.vault.delete(a["id"]))
        self.assertFalse(saved.exists())
        self.assertTrue(src.is_file())
        self.assertFalse(self.vault.delete(a["id"]))

    def test_limit_checks(self):
        with self.assertRaises(CaptureError):
            self.vault.add_text("x" * (MAX_TEXT_BYTES + 1))
        huge = self.root / "big.bin"
        with huge.open("wb") as f:
            f.truncate(MAX_FILE_BYTES + 1)
        with self.assertRaises(CaptureError):
            self.vault.add_file(huge)

    def test_empty_and_invalid_text(self):
        for content in ("", "   "):
            with self.assertRaises(CaptureError):
                self.vault.add_text(content)

    def test_search_handles_sql_symbols(self):
        self.vault.add_text("100% focus", title="x")
        self.vault.add_text("regular", title="another")
        self.assertEqual(len(self.vault.search("focus")), 1)
        self.assertEqual(len(self.vault.search("%")), 1)
        self.assertEqual(len(self.vault.search("' OR 1=1 --")), 0)

    def test_export_contains_content_and_no_file_bytes(self):
        self.vault.add_text("Private note")
        src = self.root / "note.txt"
        src.write_text("file bytes", encoding="utf-8")
        self.vault.add_file(src)
        path = self.vault.export_json(self.root / "backup.json")
        result = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(result["format"], "cerberus-v1")
        self.assertEqual(len(result["items"]), 2)
        self.assertNotIn("file bytes", path.read_text(encoding="utf-8"))

    def test_persistence_after_reopening(self):
        item = self.vault.add_text("Persistent memory")
        self.vault.close()
        self.vault = Vault(self.root / "data")
        self.assertEqual(self.vault.get(item["id"])["content"], "Persistent memory")

    def test_search_limit_is_bounded(self):
        for i in range(4):
            self.vault.add_text(f"unique item {i}")
        self.assertEqual(len(self.vault.list(limit=2)), 2)


if __name__ == "__main__":
    unittest.main()
