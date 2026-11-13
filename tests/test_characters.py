"""Replacement identities must load, animate, capture and persist offline."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cerberus.settings import CHARACTERS, Settings
try:
    from PySide6.QtWidgets import QApplication
    from cerberus.pet import CerberusPet, CarryIcon
    from cerberus.app import Controller
except ImportError:
    QApplication = None

@unittest.skipIf(QApplication is None, 'GUI extra required')
class CharacterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_all_identities_render_capture_and_reduce_motion(self):
        signatures = set()
        for name in CHARACTERS:
            with self.subTest(character=name):
                pet = CerberusPet(character=name)
                self.assertEqual(pet._sprite_source, 'raster-pack')
                signatures.add(bytes(pet._sprite.toImage().bits()))
                clip = pet._state_frames['idle']
                self.assertGreater(len(clip.frames), 1)
                self.assertTrue(clip.loop)
                for phase in ('idle', 'portal', 'dash', 'catch', 'carry', 'celebrate', 'play', 'sleep', 'wake', 'guard'):
                    pet.summon('Test offering', CarryIcon('text', None, 'TXT'))
                    pet.motion.transition(phase)
                    self.assertFalse(pet.grab().isNull(), phase)
                pet.set_reduced_motion(True)
                self.assertFalse(pet.grab().isNull())
                pet.close()
        self.assertEqual(len(signatures), 4)

    def test_switch_updates_overlay_and_persists(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, CERBERUS_HOME=folder):
            controller = Controller(self.app)
            try:
                for name in CHARACTERS:
                    controller.set_character(name)
                    self.assertEqual(Settings.load(Path(folder)).character, name)
                    self.assertEqual(controller.pet._sprite_source, 'raster-pack')
                    self.assertFalse(controller.pet.grab().isNull())
                controller.capture('text', 'Four guardians share one vault')
                self.assertEqual(len(controller.vault.search('guardians')), 1)
            finally:
                controller.gesture_hook.stop()
                controller.hotkey.unregister()
                controller.tray.hide()
                for widget in (controller.pet, controller.bubble, controller.dock, controller.window):
                    widget.close()
                controller.vault.close()
