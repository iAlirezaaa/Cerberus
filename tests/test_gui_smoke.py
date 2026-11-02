"""Qt smoke test. Runs with QT_QPA_PLATFORM=offscreen in CI."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from cerberus.pet import CerberusPet
    from cerberus.app import Controller
except ImportError:
    QApplication = None
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


if __name__ == "__main__":
    unittest.main()
