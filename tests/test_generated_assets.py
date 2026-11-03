"""Check all user-created animation files are included, without GUI imports."""
from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

from cerberus.animation_pack import parse_manifest


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "assets" / "animations"


class GeneratedAssetTests(unittest.TestCase):
    def test_sequences_and_manifest(self):
        data = (ART / "animation-pack.json").read_bytes()
        manifest = parse_manifest(data)
        self.assertEqual(len(manifest.states["portal"].frames), 8)
        self.assertFalse(manifest.states["portal"].loop)
        self.assertEqual(len(manifest.states["idle"].frames), 8)
        self.assertTrue(manifest.states["idle"].loop)
        for frame in set([manifest.default] + list(manifest.states["portal"].frames) + list(manifest.states["idle"].frames)):
            path = ART / frame
            self.assertTrue(path.is_file(), frame)
            raw = path.read_bytes()[:26]
            self.assertTrue(raw.startswith(b"\x89PNG\r\n\x1a\n"), frame)
            self.assertEqual(raw[25], 6, "Frame must have an RGBA alpha channel")

    def test_gifs_and_concepts_are_present(self):
        for name in ("cerberus_portal_enter.gif", "cerberus_bored_lookaround.gif"):
            data = (ART / name).read_bytes()
            self.assertTrue(data.startswith(b"GIF89a"), name)
        concepts = list((ROOT / "assets" / "concepts").glob("concept_*.png"))
        self.assertEqual(len(concepts), 5)

    def test_sheet_dimensions(self):
        for name in ("portal_sheet.png", "bored_sheet.png"):
            raw = (ART / "sheets" / name).read_bytes()[:26]
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", raw[16:24]), (2172, 724))


if __name__ == "__main__":
    unittest.main()
