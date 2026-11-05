import unittest

from cerberus.item_kinds import (
    clean_text, decode_text, is_runnable, kind_for, kind_for_path, preview_for_content,
    preview_mode, sniff,
)


class ItemKindTests(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(kind_for({"kind": "url", "title": "x.pdf"}), "link")
        self.assertEqual(kind_for({"kind": "text"}), "text")
        cases = {"a.PDF": "pdf", "b.docx": "document", "c.xlsx": "spreadsheet", "d.zip": "archive",
                 "e.py": "code", "f.mp3": "audio", "g.mkv": "video", "h.exe": "app",
                 "i.ttf": "font", "j.eml": "email", "k.glb": "model3d", "l.weird": "file",
                 "m.png": "image", "n.pptx": "presentation"}
        for name, kind in cases.items():
            with self.subTest(name=name):
                self.assertEqual(kind_for({"kind": "file", "original_name": name}), kind)
                self.assertEqual(kind_for_path(name), kind)

    def test_preview_modes_are_corrected_by_content(self):
        item = {"kind": "file", "original_name": "photo.png"}
        self.assertEqual(preview_mode(item), "image")
        self.assertEqual(preview_for_content("image", b"\x89PNG\r\n\x1a\n...."), "image")
        # A file named .png that is really a PDF, or junk, is not handed to an image decoder.
        self.assertEqual(preview_for_content("image", b"%PDF-1.7 ..."), "pdf")
        self.assertEqual(preview_for_content("image", b"MZ\x90\x00 exe"), "icon_only")
        self.assertEqual(preview_for_content("icon_only", b"GIF89a...."), "animated_image")
        self.assertEqual(sniff(b"RIFF\x00\x00\x00\x00WEBPVP8 "), "webp")
        self.assertIsNone(sniff(b"<svg"))
        self.assertEqual(preview_mode({"kind": "file", "original_name": "notes.md"}), "text_file")
        self.assertEqual(preview_mode({"kind": "file", "original_name": "song.mp3"}), "icon_only")

    def test_text_cleaning_and_decoding(self):
        self.assertEqual(clean_text("safe‮txt.exe\x07\n"), "safetxt.exe\n")
        self.assertEqual(decode_text("hi".encode("utf-16")), "hi")
        self.assertIsNone(decode_text(b"\x00\x01binary"))
        self.assertEqual(decode_text("﻿سلام".encode("utf-8")), "سلام")

    def test_runnable_files_are_flagged(self):
        for name in ("setup.exe", "run.BAT", "x.ps1", "y.js", "z.lnk", "m.docm"):
            self.assertTrue(is_runnable({"original_name": name}), name)
        for name in ("a.pdf", "b.png", "c.txt"):
            self.assertFalse(is_runnable({"original_name": name}), name)


if __name__ == "__main__":
    unittest.main()
