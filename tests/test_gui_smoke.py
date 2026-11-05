"""Qt smoke test. Runs with QT_QPA_PLATFORM=offscreen in CI."""
import os
import json
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from cerberus.settings import Settings

try:
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication
    from cerberus.pet import DISMISS_RECT, CarryIcon, CerberusPet, ReturnButton
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
        self.assertLessEqual(max(pet._sprite.width(), pet._sprite.height()), 768)
        self.assertTrue({"sleep", "dash", "carry", "guard", "arrive", "leave",
                         "idle_look", "idle_wag", "idle_wait", "bark"}.issubset(pet._state_frames))
        # Every bundled GIF decodes to 8 cropped, transparent frames.
        for state, clip in pet._state_frames.items():
            self.assertTrue(clip.anchored, state)
            self.assertEqual(len(clip.frames), 8, state)
            self.assertTrue(clip.frames[0].toImage().hasAlphaChannel(), state)
            self.assertEqual(clip.frames[0].toImage().pixelColor(0, 0).alpha(), 0, state)
        self.assertIs(pet._frame_for_state("idle", pet.motion.entered_at),
                      pet._state_frames["idle"].frames[0])
        self.assertEqual(pet._sprite.toImage().pixelColor(0, 0).alpha(), 0)
        sleep = pet._state_frames["sleep"]
        # Fall-asleep plays once, then loops only the sleeping frames.
        self.assertEqual(sleep.index_at(sleep.total + 0.01), 4)
        self.assertEqual(pet._state_frames["catch"].index_at(99), 7)
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

    def test_runs_off_screen_then_returns_on_summon(self):
        pet = CerberusPet(away_seconds=60)
        pet.show()
        self.app.processEvents()
        start_x = pet.x()
        pet.motion.transition("leave")
        for _ in range(400):
            pet._last_tick -= 0.05  # simulate 50 ms between ticks
            pet._tick()
            if pet._phase == "away":
                break
        self.assertEqual(pet._phase, "away")
        self.assertFalse(pet.isVisible())
        self.assertFalse(pet._timer.isActive())
        self.assertNotEqual(pet.x(), start_x)
        pet.arrive("I'm back!")
        self.app.processEvents()
        self.assertEqual(pet._phase, "arrive")
        self.assertTrue(pet.isVisible())
        self.assertTrue(pet._timer.isActive())
        screen = pet.screen().availableGeometry()
        self.assertTrue(screen.contains(pet.geometry().center()))
        self.assertFalse(pet.grab().isNull())
        pet.close()

    def test_walks_faces_cursor_and_draws_carried_icon(self):
        pet = CerberusPet(roam=True, chat_level="chatty", language="fa")
        pet.show()
        self.app.processEvents()
        pet.move(pet._area().left() + 40, pet.y())
        now = time.monotonic()
        self.assertTrue(pet._start_walk(now))
        self.assertEqual(pet._phase, "walk")
        self.assertEqual(pet._visual_state("walk"), "walk")
        start = pet.x()
        for _ in range(2000):
            pet._last_tick -= 0.05
            pet._tick()
            if pet._phase != "walk":
                break
        self.assertEqual(pet._phase, "idle")
        self.assertEqual(pet.x(), round(pet._walk_target))
        self.assertNotEqual(pet.x(), start)
        # Mirrored frames are cached, not re-created on every paint.
        pet._facing = -1
        self.assertFalse(pet.grab().isNull())
        self.assertFalse(pet.grab().isNull())
        self.assertLessEqual(len(pet._mirrored), 2)
        # Carry clips know where the document is and paint the caught item's icon.
        carry = pet._state_frames["carry"]
        self.assertEqual(len(carry.props), 8)
        self.assertIsNone(pet._state_frames["catch"].props[0])
        image = QImage(20, 20, QImage.Format.Format_ARGB32)
        image.fill(QColor(0, 120, 255))
        from PySide6.QtGui import QPixmap
        pet.summon("Saved!", CarryIcon("image", QPixmap.fromImage(image), "PNG"))
        pet.motion.transition("carry")
        self.assertFalse(pet.grab().isNull())
        # Speech uses the Persian quip book and survives painting.
        pet.say("pet", force=True)
        self.assertTrue(pet._message)
        self.assertFalse(pet.grab().isNull())
        # Waking up is the fall-asleep clip played backwards.
        wake = pet._state_frames["wake"]
        sleep = pet._state_frames["sleep"]
        self.assertIs(wake.frames[0], sleep.frames[-1])
        pet.close()

    def test_dismiss_button_and_return_dock(self):
        pet = CerberusPet()
        pet.show()
        self.app.processEvents()
        fired = []
        pet.dismiss_requested.connect(lambda: fired.append(True))
        pet._hovered = True
        self.assertTrue(pet._dismiss_visible())
        self.assertFalse(pet.grab().isNull())
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QEvent, Qt as QtNS
        centre = DISMISS_RECT.center()
        local = QPointF(centre.x() * pet.width() / 340, centre.y() * pet.height() / 380)
        press = QMouseEvent(QEvent.Type.MouseButtonPress, local, pet.mapToGlobal(local),
                            QtNS.MouseButton.LeftButton, QtNS.MouseButton.LeftButton,
                            QtNS.KeyboardModifier.NoModifier)
        pet.mousePressEvent(press)
        self.assertEqual(fired, [True])
        sides = []
        pet.went_away.connect(lambda side, y: sides.append(side))
        pet.dismiss()
        self.assertEqual(pet._phase, "leave")
        for _ in range(600):
            pet._last_tick -= 0.05
            pet._tick()
            if pet._phase == "away":
                break
        self.assertEqual(pet._phase, "away")
        self.assertEqual(len(sides), 1)
        dock = ReturnButton(pet._sprite)
        clicks = []
        dock.clicked.connect(lambda: clicks.append(1))
        dock.show_at(sides[0], 800)
        self.assertTrue(dock.isVisible())
        self.assertFalse(dock.grab().isNull())
        dock.clicked.emit()
        self.assertEqual(clicks, [1])
        dock.hide()
        dock.close()
        pet.close()

    def test_idle_rotates_between_clips(self):
        pet = CerberusPet()
        seen = set()
        now = 1000.0
        for _ in range(60):
            pet._pick_idle_variant(now)
            seen.add(pet._visual_state("idle"))
            now += 10
        self.assertGreaterEqual(len(seen), 3)
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
                self.assertEqual(controller.window.stat_labels["total"].text(), "2")
                self.assertEqual(controller.window.detail_title.text(), "captured-image.png")
                self.assertIn("FILE ATTACHMENT", controller.window.preview.text())
                controller.window.search_box.setText("visual")
                self.app.processEvents()
                self.assertEqual(controller.window.items.count(), 1)
                self.assertIn("visual smoke-test", controller.window.detail_body.text())
                self.assertEqual(controller.window.preview.text(), "MEMORY PREVIEW")
                # File capture carries the file-type label for the paw icon.
                note = Path(folder) / "report.pdf"
                note.write_bytes(b"%PDF-1.4 smoke")
                controller.capture("files", [str(note)])
                self.assertEqual(controller.pet._carry.label, "PDF")
                # Settings window shows where memories live and can move them.
                controller.open_settings()
                self.app.processEvents()
                window = controller.settings_window
                self.assertIn(str(controller.vault.home.resolve()), window.storage_path.text())
                self.assertIn("3 memories", window.storage_details.text())
                self.assertTrue(window.shortcut_status.text())
                new_home = Path(folder) / "moved-vault"
                controller.change_storage(new_home, copy_existing=True)
                self.assertEqual(controller.vault.home.resolve(), new_home.resolve())
                self.assertEqual(len(controller.vault.list()), 3)
                self.assertEqual(Settings.load(controller.home).storage_dir,
                                 str(new_home.resolve()))
                controller.set_hotkey("Ctrl+Alt+Shift+F11")
                controller.set_mouse_gesture("off")
                controller.set_chat_level("chatty")
                controller.set_language("fa")
                self.assertEqual(controller.pet.quips.language, "fa")
                window.refresh()
                window.close()
            finally:
                if controller is not None:
                    controller.gesture_hook.stop()
                    controller.hotkey.unregister()
                    controller.dock.close()
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
