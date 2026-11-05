"""Desktop controller, system tray, clipboard opt-in and search UI."""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QFileInfo, QIODevice, QLocale, QPoint, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QImageReader, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFileIconProvider, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton, QSystemTrayIcon,
    QVBoxLayout, QWidget,
)

from .pet import CarryIcon, CerberusPet, MiniBubble, mime_image_png
from .quips import resolve_language
from .settings import Settings, data_dir, vault_dir
from .settings_window import SettingsWindow, prompt_storage_change
from .vault_window import VaultWindow
from .shortcuts import MOUSE_GESTURES, SHORTCUT_ACTIONS, ChordEdge
from .vault import CaptureError, Vault
from .win_input import IS_WINDOWS, GlobalHotkey, MouseGestureHook, read_buttons


def tray_icon(sprite: QPixmap | None = None) -> QIcon:
    """Cerberus's own heads as the tray icon, with a drawn fallback."""
    if sprite is not None and not sprite.isNull():
        heads = sprite.copy(0, 0, sprite.width(), int(sprite.height() * .6))
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        scaled = heads.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        p = QPainter(pixmap)
        p.drawPixmap((64 - scaled.width()) // 2, (64 - scaled.height()) // 2, scaled)
        p.end()
        return QIcon(pixmap)
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#25313c"))
    for x, y in [(5, 18), (23, 7), (41, 18)]:
        p.drawEllipse(x, y, 20, 24)
    p.drawEllipse(12, 28, 40, 30)
    p.setBrush(QColor("#ffaf54"))
    for x, y in [(12, 28), (30, 17), (48, 28)]:
        p.drawEllipse(x, y, 5, 5)
    p.end()
    return QIcon(pixmap)


class Controller:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.home = data_dir()
        self.settings = Settings.load(self.home)
        self._storage_warning = ""
        try:
            self.vault = Vault(vault_dir(self.home, self.settings))
        except (OSError, sqlite3.Error) as exc:
            # A custom folder on a removed drive must not stop the app.
            self._storage_warning = f"Storage folder unavailable ({exc}); using the default."
            self.vault = Vault(self.home)
        self.window = VaultWindow(self.vault, change_storage=self.ask_change_storage)
        self.settings_window: SettingsWindow | None = None
        self.pet = CerberusPet(
            reduced_motion=self.settings.reduced_motion,
            standby_seconds=self.settings.standby_seconds,
            away_seconds=self.settings.away_seconds if self.settings.wander_off else None,
            roam=self.settings.roam,
            chat_level=self.settings.chat_level,
            language=self._language(),
        )
        self.pet.set_pet_size(self.settings.pet_size)
        self.pet.capture_requested.connect(self.capture)
        self.pet.vault_requested.connect(self.open_vault)
        self.pet.menu_requested.connect(self.open_menu)
        self.pet.dismiss_requested.connect(self.send_away)
        self.pet.went_away.connect(self.pet_went_away)
        self.pet.minimize_requested.connect(self.minimize)
        self.pet.came_back.connect(self.pet_came_back)
        # Docked at the screen edge while Cerberus is away.
        self.dock = MiniBubble(self.pet._sprite, reduced_motion=self.settings.reduced_motion)
        self.dock.clicked.connect(self.summon_pet)
        self.dock.dropped.connect(self.capture)
        self.dock.menu_requested.connect(self.open_menu)
        # The minimized Cerberus: a bubble that still accepts drops.
        self.minimized = False
        self.bubble = MiniBubble(self.pet._sprite, self.pet._state_frames.get("mini_curl"),
                                 size=84, reduced_motion=self.settings.reduced_motion)
        self.bubble.clicked.connect(self.restore)
        self.bubble.dropped.connect(self.capture)
        self.bubble.moved.connect(self.bubble_moved)
        self.bubble.menu_requested.connect(self.open_menu)
        self.tray = QSystemTrayIcon(tray_icon(self.pet._sprite), app)
        self.tray.setToolTip("Cerberus — your memory guardian")
        self.menu = QMenu()
        show = self.menu.addAction("Show / hide Cerberus")
        show.triggered.connect(self.toggle_pet)
        self.menu.addAction("Open memory vault", self.open_vault)
        self.menu.addAction("Settings…", self.open_settings)
        self.menu.addAction("Feed current clipboard", self.feed_clipboard)
        self.menu.addSeparator()
        self.menu.addAction("Call Cerberus here", self.summon_pet)
        self.menu.addAction("Send Cerberus away", self.send_away)
        self.menu.addAction("Minimize / restore", self.toggle_minimized)
        self.menu.addAction("Play with Cerberus", lambda: self.pet.play("play"))
        self.menu.addAction("Guard the vault", lambda: self.pet.play("guard"))
        self.menu.addAction("Sleep / standby", lambda: self.pet.play("sleep"))
        sizes = self.menu.addMenu("Pet size")
        for label, size in (("Small", 230), ("Medium", 340), ("Large", 450)):
            sizes.addAction(label, lambda checked=False, target=size: self.set_pet_size(target))
        self.menu.addSeparator()
        self.clipboard_action = QAction("Auto-capture newly copied clipboard items", self.menu)
        self.clipboard_action.setCheckable(True)
        self.clipboard_action.setChecked(self.settings.clipboard_capture)
        self.clipboard_action.toggled.connect(self.set_clipboard)
        self.menu.addAction(self.clipboard_action)
        self.motion_action = QAction("Reduced motion", self.menu)
        self.motion_action.setCheckable(True)
        self.motion_action.setChecked(self.settings.reduced_motion)
        self.motion_action.toggled.connect(self.set_reduced_motion)
        self.menu.addAction(self.motion_action)
        self.menu.addSeparator()
        self.menu.addAction("Quit Cerberus", self.app.quit)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()
        # Summon shortcuts: see cerberus/shortcuts.py and cerberus/win_input.py.
        self.gesture_hook = MouseGestureHook()
        self.gesture_hook.triggered.connect(self.shortcut_fired)
        self.hotkey = GlobalHotkey()
        self.hotkey.triggered.connect(self.shortcut_fired)
        self.chord = ChordEdge()
        self.chord_timer = QTimer()
        self.chord_timer.setInterval(40)
        self.chord_timer.timeout.connect(self.poll_chord)
        self._hotkey_ok = False
        self.apply_shortcuts()
        self.app.clipboard().dataChanged.connect(self.clipboard_changed)
        self.app.aboutToQuit.connect(self.shutdown)
        if self.settings.show_pet and self.settings.minimized:
            self._start_minimized()
        elif self.settings.show_pet:
            self.pet.show()
            QTimer.singleShot(1200, self.pet.greet)
        if self._storage_warning:
            QTimer.singleShot(1500, lambda: self.pet.tell(self._storage_warning, seconds=6))
        self.app.setQuitOnLastWindowClosed(False)

    def _language(self) -> str:
        return resolve_language(self.settings.language, QLocale.system().name())

    def shutdown(self) -> None:
        self.bubble.hide()
        self.dock.hide()
        self.gesture_hook.stop()
        self.hotkey.unregister()
        self.chord_timer.stop()
        self.vault.close()

    # ----- shortcuts -------------------------------------------------------
    def apply_shortcuts(self) -> None:
        self.chord_timer.stop()
        mode = self.settings.mouse_gesture
        hooked = self.gesture_hook.start(mode)
        if not hooked and mode == "left_right" and IS_WINDOWS:
            # Fallback: still summons, but cannot stop the right-click menu.
            self.chord_timer.start()
        self._hotkey_ok = self.hotkey.register(self.settings.hotkey) if self.settings.hotkey else False

    def shortcut_status(self) -> str:
        parts = []
        mode = self.settings.mouse_gesture
        if mode == "off":
            parts.append("Mouse gesture off.")
        elif self.gesture_hook.active:
            parts.append(f"Mouse: {MOUSE_GESTURES[mode]} — active.")
        elif self.chord_timer.isActive():
            parts.append("Mouse: left + right works, but the right-click can't be blocked here.")
        else:
            parts.append("Mouse gestures need Windows.")
        if not self.settings.hotkey:
            parts.append("No keyboard shortcut.")
        elif self._hotkey_ok:
            parts.append(f"Keyboard: {self.settings.hotkey} — active.")
        elif IS_WINDOWS:
            parts.append(f"Keyboard: {self.settings.hotkey} is already used by another app; pick another.")
        else:
            parts.append("Keyboard shortcuts need Windows.")
        return " ".join(parts)

    def poll_chord(self) -> None:
        left, right = read_buttons()
        if self.chord.feed(left, right, time.monotonic()):
            self.shortcut_fired()

    def shortcut_fired(self) -> None:
        action = self.settings.shortcut_action
        if action == "minimize":
            self.toggle_minimized()
        elif (action == "toggle" and not self.minimized and self.pet.isVisible()
              and not self.pet.is_away):
            self.send_away()
        else:
            self.summon_pet()

    # ----- presence --------------------------------------------------------
    def summon_pet(self, *_: object) -> None:
        """Bring Cerberus to the mouse cursor through the portal (from any state)."""
        if self.minimized:
            self.restore(at_cursor=True)
            return
        if not self.settings.show_pet:
            self.settings.show_pet = True
            self._save()
        self.dock.hide()
        was_away = self.pet.is_away or not self.pet.isVisible()
        self.pet.arrive(self.pet.quips.pick("arrive") if was_away else "")

    # ----- minimized mode --------------------------------------------------
    #   state      | minimize          | restore / summon      | send away | capture
    #   visible    | portal -> bubble  | (summon: to cursor)   | runs off  | pet celebrates
    #   away       | dock -> bubble    | portal at cursor      | -         | pet returns
    #   hidden     | bubble            | shown at cursor       | -         | pet returns
    #   minimized  | restore           | at bubble / cursor    | -         | bubble flashes
    def minimize(self, *_: object) -> None:
        if self.minimized:
            return
        self.minimized = True
        self.dock.hide()
        feet = (self.pet.feet_position()
                if self.pet.isVisible() and not self.pet.is_away else None)

        def finish() -> None:
            if not self.minimized:  # restored while the exit clip played
                return
            self.pet.freeze()
            if feet is not None:
                self.bubble.show_centered(feet)
            else:
                self._show_bubble_at_saved()
            self.settings.minimized = True
            self.settings.bubble_x, self.settings.bubble_y = self.bubble.x(), self.bubble.y()
            self._save()

        if feet is not None:
            self.pet.vanish(finish)
        else:
            finish()

    def _show_bubble_at_saved(self) -> None:
        if self.settings.bubble_x >= 0 and self.settings.bubble_y >= 0:
            self.bubble.move(self.bubble._clamp(QPoint(self.settings.bubble_x,
                                                       self.settings.bubble_y)))
            self.bubble._show()
        else:
            screen = QApplication.primaryScreen()
            area = screen.availableGeometry() if screen else None
            if area is None:
                return
            self.bubble.show_centered(QPoint(area.right() - 80, area.bottom() - 10))

    def _start_minimized(self) -> None:
        self.minimized = True
        self.pet.freeze()
        self._show_bubble_at_saved()

    def restore(self, *_: object, at_cursor: bool = False) -> None:
        if not self.minimized:
            return
        self.minimized = False
        point = self.bubble.geometry().center()
        point.setY(self.bubble.geometry().bottom())
        self.bubble.hide()
        self.settings.minimized = False
        self.settings.show_pet = True
        self._save()
        message = self.pet.quips.pick("arrive")
        if at_cursor:
            self.pet.arrive(message)
        else:
            self.pet.arrive(message, at=point)

    def toggle_minimized(self, *_: object) -> None:
        if self.minimized:
            self.restore()
        else:
            self.minimize()

    def bubble_moved(self, point) -> None:
        if self.minimized:
            self.settings.bubble_x, self.settings.bubble_y = point.x(), point.y()
            self._save()

    def send_away(self, *_: object) -> None:
        if not self.minimized:
            self.pet.dismiss()

    def pet_went_away(self, side: int, bottom_y: int) -> None:
        if self.settings.show_return_button:
            self.dock.show_at(side, bottom_y, self.pet.screen())

    def pet_came_back(self) -> None:
        self.dock.hide()

    def tray_activated(self, reason) -> None:
        # One click minimizes / restores. (A double-click also starts with this click,
        # so it is not given a second, conflicting meaning.)
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_minimized()

    def open_menu(self, where) -> None:
        self.menu.exec(where)

    def open_vault(self, *_: object) -> None:
        self.window.refresh()
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def open_settings(self, *_: object) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self)
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def toggle_pet(self, *_: object) -> None:
        if self.minimized or self.pet.is_away:
            self.summon_pet()
            return
        visible = not self.pet.isVisible()
        if visible:
            self.pet.arrive()
        else:
            self.pet.hide()
            self.dock.hide()
        self.settings.show_pet = visible
        self._save()

    # ----- settings (also driven by SettingsWindow) ------------------------
    def _save(self) -> None:
        self.settings.save(self.home)

    def set_clipboard(self, enabled: bool) -> None:
        self.settings.clipboard_capture = enabled
        self._save()
        if self.clipboard_action.isChecked() != enabled:
            self.clipboard_action.setChecked(enabled)
        self.pet.tell("Clipboard capture ON" if enabled else "Clipboard capture OFF")

    def set_pet_size(self, size: int) -> None:
        self.pet.set_pet_size(size)
        self.settings.pet_size = self.pet.width()
        self._save()

    def set_reduced_motion(self, enabled: bool) -> None:
        self.settings.reduced_motion = enabled
        self.pet.set_reduced_motion(enabled)
        self.bubble.reduced_motion = self.dock.reduced_motion = enabled
        if self.motion_action.isChecked() != enabled:
            self.motion_action.setChecked(enabled)
        self._save()

    def set_wander_off(self, enabled: bool) -> None:
        self.settings.wander_off = enabled
        self._save()
        self.pet.set_away_after(self.settings.away_seconds if enabled else None)

    def set_away_minutes(self, minutes: int) -> None:
        self.settings.away_seconds = max(30, min(7200, int(minutes) * 60))
        self._save()
        if self.settings.wander_off:
            self.pet.set_away_after(self.settings.away_seconds)

    def set_standby_seconds(self, seconds: int) -> None:
        self.settings.standby_seconds = max(15, min(3600, int(seconds)))
        self.pet.motion.standby_after = self.settings.standby_seconds
        self._save()

    def set_return_button(self, enabled: bool) -> None:
        self.settings.show_return_button = enabled
        self._save()
        if not enabled:
            self.dock.hide()

    def set_roam(self, enabled: bool) -> None:
        self.settings.roam = enabled
        self.pet.set_roam(enabled)
        self._save()

    def set_chat_level(self, level: str) -> None:
        self.settings.chat_level = level
        self.pet.set_chat_level(level)
        self._save()

    def set_language(self, language: str) -> None:
        self.settings.language = language
        self._save()
        self.pet.set_language(self._language())
        self.pet.say("wake", force=True)

    def set_mouse_gesture(self, mode: str) -> None:
        if mode in MOUSE_GESTURES:
            self.settings.mouse_gesture = mode
            self._save()
            self.apply_shortcuts()

    def set_hotkey(self, text: str) -> None:
        self.settings.hotkey = text
        self._save()
        self.apply_shortcuts()

    def set_shortcut_action(self, action: str) -> None:
        if action in SHORTCUT_ACTIONS:
            self.settings.shortcut_action = action
            self._save()

    def ask_change_storage(self, parent) -> None:
        prompt_storage_change(self, parent)
        if self.settings_window is not None:
            self.settings_window.refresh_storage()

    def change_storage(self, folder: Path, *, copy_existing: bool) -> None:
        """Point the vault at another folder, optionally copying current memories."""
        folder = Path(folder).resolve()
        if copy_existing and not Vault.has_vault(folder):
            self.vault.copy_to(folder)
        new_vault = Vault(folder)
        old = self.vault
        self.vault = new_vault
        self.window.set_vault(new_vault)
        old.close()
        self.settings.storage_dir = "" if folder == self.home.resolve() else str(folder)
        self._save()
        if self.window.isVisible():
            self.window.refresh()
        self.pet.tell("New den, same guardian!" if self.pet.quips.language == "en"
                      else "لونه‌ی جدید، همون نگهبان!")

    # ----- capture ---------------------------------------------------------
    def _clipboard_payload(self) -> tuple[str, object] | None:
        mime = self.app.clipboard().mimeData()
        if mime is None:
            return None
        if mime.hasUrls():
            files = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
            if files:
                return "files", files
        if mime.hasText() and mime.text().strip():
            return "text", mime.text()
        if mime.hasImage():
            png = mime_image_png(mime)
            if png:
                return "image", png
        return None

    def clipboard_changed(self) -> None:
        if self.settings.clipboard_capture:
            self.feed_clipboard()

    def feed_clipboard(self, *_: object) -> None:
        payload = self._clipboard_payload()
        if payload:
            self.capture(*payload)

    def capture(self, kind: str, value: object) -> None:
        quips = self.pet.quips
        try:
            if kind == "files":
                paths = list(value)
                if not paths:
                    return
                items = [self.vault.add_file(Path(path), source="drop-or-clipboard")
                         for path in paths]
                carry = carry_icon_for_file(Path(paths[0]), items[0].get("stored_path"))
                message = (quips.pick("capture_file", name=Path(paths[0]).name)
                           if len(paths) == 1 else quips.pick("capture_files", count=len(paths)))
            elif kind == "text":
                item = self.vault.capture_text(str(value), source="drop-or-clipboard")
                carry = CarryIcon("url" if item["kind"] == "url" else "text")
                message = quips.pick("capture_url" if item["kind"] == "url" else "capture_text")
            elif kind == "image":
                self.vault.add_bytes(bytes(value), name="captured-image.png", source="drop-or-clipboard")
                carry = CarryIcon("image", image_thumbnail(bytes(value)), "IMG")
                message = quips.pick("capture_image")
            else:
                return
            total = self.vault.stats()["total"]
            if total in MILESTONES:
                message = quips.pick("milestone", total=total)
            if self.window.isVisible():
                self.window.refresh()
        except (CaptureError, OSError, ValueError) as exc:
            if self.minimized:
                # Stay small: a tray notice instead of a dialog or the pet popping up.
                self.bubble.flash(quips.pick("error"))
                self.tray.showMessage("Cerberus couldn't save that", str(exc)[:200],
                                      QSystemTrayIcon.MessageIcon.Warning, 4000)
                return
            self.pet.sad()
            self.pet.tell(f'{quips.pick("error")} ({exc})'[:90])
            QMessageBox.warning(self.window, "Cerberus — Capture error", str(exc))
            return
        self.celebrate(message, carry)

    def celebrate(self, message: str, carry: CarryIcon | None) -> None:
        """Show that something was saved: the bubble flashes when minimized."""
        if self.minimized:
            self.bubble.flash(message)
            return
        self.dock.hide()
        self.pet.summon(message, carry)


MILESTONES = {10, 25, 50, 100, 250, 500, 1000, 2500, 5000}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


def image_thumbnail(data: bytes | None = None, path: Path | None = None,
                    size: int = 64) -> QPixmap | None:
    """Small bounded thumbnail of an image (bytes or a file inside the vault)."""
    buffer = None
    if data is not None:
        buffer = QBuffer()
        buffer.setData(QByteArray(data))
        if not buffer.open(QIODevice.OpenModeFlag.ReadOnly):
            return None
        reader = QImageReader(buffer)
    elif path is not None and path.is_file():
        reader = QImageReader(str(path))
    else:
        return None
    dimensions = reader.size()
    if not dimensions.isValid() or dimensions.width() * dimensions.height() > 40_000_000:
        return None
    reader.setScaledSize(dimensions.scaled(QSize(size, size), Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    if buffer is not None:
        buffer.close()
    return None if image.isNull() else QPixmap.fromImage(image)


def carry_icon_for_file(original: Path, stored: str | None) -> CarryIcon:
    """The file's own thumbnail (images) or its system file-type icon."""
    label = original.suffix.lstrip(".").upper()[:4] or "FILE"
    if original.suffix.lower() in IMAGE_SUFFIXES and stored:
        thumb = image_thumbnail(path=Path(stored))
        if thumb is not None:
            return CarryIcon("image", thumb, label)
    icon = QFileIconProvider().icon(QFileInfo(str(original)))
    pixmap = icon.pixmap(48, 48) if not icon.isNull() else None
    return CarryIcon("file", pixmap if pixmap is not None and not pixmap.isNull() else None, label)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Cerberus")
    app.setQuitOnLastWindowClosed(False)
    controller = Controller(app)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
