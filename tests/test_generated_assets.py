"""Validate the replacement source assets shipped with the app."""
from pathlib import Path
import unittest
import json
import struct
ROOT = Path(__file__).resolve().parents[1] / 'cerberus/assets/characters'
class GeneratedAssetTests(unittest.TestCase):
    def test_exact_four_characters_and_sources(self):
        self.assertEqual({p.name for p in ROOT.iterdir() if p.is_dir()}, {'ghost','hades','charon','cerberus'})
        for root in ROOT.iterdir():
            if not root.is_dir(): continue
            manifest=json.loads((root/'animation-pack.json').read_text())
            self.assertEqual(manifest['states']['idle']['gif'], 'performance.gif')
            self.assertTrue(manifest['states']['idle']['loop'])
            raw=(root/'performance.gif').read_bytes()
            self.assertEqual(raw[:6],b'GIF89a')
            self.assertEqual(struct.unpack('<HH',raw[6:10]),(384,512))
            frames=sorted(root.glob('[0-9][0-9].png'))
            self.assertEqual(len(frames),16)
            self.assertGreater(len({p.read_bytes() for p in frames}),8)
            for p in frames:
                raw=p.read_bytes()
                self.assertEqual(raw[:8],b'\x89PNG\r\n\x1a\n')
                self.assertEqual(raw[25],6)
    def test_no_previous_mascot_assets(self):
        assets=ROOT.parent
        for name in ('guardian.svg','guardian-ember.png','animation-pack.json','clips','gifs','behaviors'):
            self.assertFalse((assets/name).exists(), name)
