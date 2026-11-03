"""Qt smoke test. Runs with QT_QPA_PLATFORM=offscreen in CI."""
import os
import json
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication
    from cerberus.pet import CerberusPet
    from cerberus.app import Controller
except ImportError:
    QApplication = None
    QByteArray = QBuffer = QIODevice = QColor = QImage = None
    CerberusPet = None
    Controller = None


@unittest.skipIf(QApplication is None, "Install cerberus[gui] to run GUI smoke tests")
class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_mascot_renders_and_enters_portal_state(self):
        pet = CerberusPet(reduced_motion=False)
        pet.show()
        self.app.processEvents()
        self.assertFalse(pet.grab().isNull())
        self.assertFalse(pet._sprite.isNull())
        self.assertEqual(pet._sprite_source, "raster-pack")
        self.assertTrue(pet._sprite.toImage().hasAlphaChannel())
        self.assertIs(pet._frame_for_state("idle", pet.motion.entered_at), pet._sprite)
        self.assertEqual(pet._sprite.toImage().pixelColor(0, 0).alpha(), 0)
        pet.set_pet_size(230)
        self.assertEqual(pet.width(), 230)
        pet.summon("Capture!")
        self.app.processEvents()
        self.assertEqual(pet._phase, "portal")
        self.assertFalse(pet.grab().isNull())
        pet.play("sleep")
        self.assertEqual(pet._phase, "sleep")
        pet.play("wake")
        self.assertEqual(pet._phase, "wake")
        pet.set_reduced_motion(True)
        self.assertTrue(pet.reduced_motion)
        pet.close()

    def test_controller_capture_and_search(self):
        with tempfile.TemporaryDirectory() as folder:
            previous = os.environ.get("CERBERUS_HOME")
            os.environ["CERBERUS_HOME"] = str(Path(folder) / "vault")
            controller = None
            try:
                controller = Controller(self.app)
                controller.capture("text", "A visual smoke-test memory")
                self.assertEqual(len(controller.vault.search("smoke")), 1)
                controller.capture("image", b"test-image-bytes")
                self.assertEqual(len(controller.vault.list()), 2)
                controller.open_vault()
                self.app.processEvents()
                self.assertEqual(controller.window.items.count(), 2)
            finally:
                if controller is not None:
                    controller.tray.hide()
                    controller.pet.close()
                    controller.window.close()
                    controller.vault.close()
                if previous is None:
                    os.environ.pop("CERBERUS_HOME", None)
                else:
                    os.environ["CERBERUS_HOME"] = previous

    def test_custom_pack_frames_follow_motion_timeline(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            previous = os.environ.get("CERBERUS_ASSET_PACK")
            frames = []
            for name, color in (("first.png", QColor(255, 0, 0, 128)),
                                ("second.png", QColor(0, 255, 0, 128))):
                image = QImage(8, 8, QImage.Format.Format_ARGB32)
                image.fill(color)
                data = QByteArray()
                buffer = QBuffer(data)
                self.assertTrue(buffer.open(QIODevice.OpenModeFlag.WriteOnly))
                self.assertTrue(image.save(buffer, "PNG"))
                buffer.close()
                (root / name).write_bytes(bytes(data))
                frames.append(name)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps({
                "format": "cerberus-animation-pack",
                "version": 1,
                "default": frames[0],
                "states": {"idle": {"frames": frames, "fps": 2, "loop": True}},
            }), encoding="utf-8")
            os.environ["CERBERUS_ASSET_PACK"] = str(manifest_path)
            pet = None
            try:
                pet = CerberusPet()
                self.assertEqual(pet._sprite_source, "raster-pack")
                pet.motion.transition("idle", now=10.0)
                first = pet._frame_for_state("idle", 10.1).toImage().pixelColor(0, 0)
                second = pet._frame_for_state("idle", 10.6).toImage().pixelColor(0, 0)
                self.assertNotEqual(first, second)
            finally:
                if pet is not None:
                    pet.close()
                if previous is None:
                    os.environ.pop("CERBERUS_ASSET_PACK", None)
                else:
                    os.environ["CERBERUS_ASSET_PACK"] = previous


if __name__ == "__main__":
    unittest.main()
