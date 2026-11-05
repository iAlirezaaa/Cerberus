"""Desktop controller, system tray, clipboard opt-in and search UI."""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QFileInfo, QIODevice, QLocale, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QImageReader, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFileIconProvider, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton, QSystemTrayIcon,
    QVBoxLayout, QWidget,
)

from .pet import CarryIcon, CerberusPet, ReturnButton, mime_image_png
from .quips import resolve_language
from .settings import Settings, data_dir, vault_dir
from .settings_window import SettingsWindow
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


class VaultWindow(QWidget):
    def __init__(self, vault: Vault) -> None:
        super().__init__()
        self.vault = vault
        self.setWindowTitle("Cerberus — Memory Archive")
        self.resize(920, 640)
        self.setMinimumSize(720, 500)
        self.setStyleSheet("""
            QWidget { background: #100d11; color: #eee7df; font-size: 13px; }
            QLabel#eyebrow { color: #f08a55; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
            QLabel#title { color: #fff2df; font-size: 26px; font-weight: 700; }
            QLabel#muted { color: #a99b98; }
            QFrame#statCard, QFrame#detailCard { background: #19151b; border: 1px solid #3a2930; border-radius: 12px; }
            QLabel#statValue { color: #ffc27c; font-size: 22px; font-weight: 700; }
            QLabel#statLabel { color: #b8a8a1; font-size: 11px; }
            QLineEdit, QListWidget, QTextEdit { background: #171319; border: 1px solid #49333a;
              border-radius: 9px; padding: 10px; selection-background-color: #6e342d; }
            QListWidget::item { padding: 10px 8px; border-bottom: 1px solid #2a2028; }
            QListWidget::item:selected { background: #302027; border-radius: 6px; color: #ffd5a2; }
            QPushButton { background: #592d2a; border: 1px solid #a34e38; border-radius: 8px; padding: 9px 14px; }
            QPushButton:hover { background: #793d30; }
            QPushButton#secondary { background: #211a22; border-color: #4b3741; }
            QPushButton#secondary:hover { background: #33232b; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)
        eyebrow = QLabel("CERBERUS  /  PRIVATE MEMORY")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)
        title_row = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("The Archive")
        title.setObjectName("title")
        subtitle = QLabel("Everything you entrust to your guardian, gathered in one place.")
        subtitle.setObjectName("muted")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        title_row.addLayout(title_block, 1)
        export_button = QPushButton("Export archive JSON")
        export_button.setObjectName("secondary")
        export_button.clicked.connect(self.export_archive)
        title_row.addWidget(export_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(title_row)

        stats_row = QHBoxLayout()
        self.stat_labels: dict[str, QLabel] = {}
        for key, label in (("total", "MEMORIES GUARDED"), ("text", "TEXT NOTES"), ("file", "FILES & IMAGES")):
            card = QFrame()
            card.setObjectName("statCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 10, 14, 10)
            value = QLabel("0")
            value.setObjectName("statValue")
            caption = QLabel(label)
            caption.setObjectName("statLabel")
            card_layout.addWidget(value)
            card_layout.addWidget(caption)
            stats_row.addWidget(card)
            self.stat_labels[key] = value
        stats_row.addStretch(1)
        layout.addLayout(stats_row)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search your saved memories…")
        self.search_box.textChanged.connect(self.refresh)
        layout.addWidget(self.search_box)

        content_row = QHBoxLayout()
        self.items = QListWidget()
        self.items.itemDoubleClicked.connect(self.open_selected)
        self.items.currentItemChanged.connect(self.show_details)
        content_row.addWidget(self.items, 3)
        detail = QFrame()
        detail.setObjectName("detailCard")
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(16, 16, 16, 16)
        self.preview = QLabel("Select a memory to inspect it")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(170)
        self.preview.setStyleSheet("background:#110e13; border-radius:9px; color:#8e7c7c; padding:10px;")
        self.preview.setWordWrap(True)
        self.detail_title = QLabel("Your memories")
        self.detail_title.setWordWrap(True)
        self.detail_title.setStyleSheet("font-size:17px;font-weight:700;color:#ffe3bf;")
        self.detail_meta = QLabel("Choose an item from the archive")
        self.detail_meta.setObjectName("muted")
        self.detail_meta.setWordWrap(True)
        self.detail_body = QLabel("A private collection, stored locally on this device.")
        self.detail_body.setWordWrap(True)
        self.detail_body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail_body.setStyleSheet("color:#d3c8c2; line-height:1.35;")
        detail_layout.addWidget(self.preview, 2)
        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_meta)
        detail_layout.addWidget(self.detail_body, 3)
        content_row.addWidget(detail, 2)
        layout.addLayout(content_row, 1)

        row = QHBoxLayout()
        for label, callback in [
            ("Copy text / URL", self.copy_selected),
            ("Open saved file", self.open_selected),
            ("Delete", self.delete_selected),
        ]:
            button = QPushButton(label)
            button.setObjectName("secondary" if label != "Delete" else "")
            button.clicked.connect(callback)
            row.addWidget(button)
        row.addStretch(1)
        refresh_button = QPushButton("Refresh")
        refresh_button.setObjectName("secondary")
        refresh_button.clicked.connect(self.refresh)
        row.addWidget(refresh_button)
        layout.addLayout(row)
        self.refresh()

    def selected(self) -> dict | None:
        item = self.items.currentItem()
        return self.vault.get(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def refresh(self, *_: object) -> None:
        selected = self.selected()
        selected_id = selected["id"] if selected else None
        self.items.clear()
        stats = self.vault.stats()
        self.stat_labels["total"].setText(str(stats["total"]))
        self.stat_labels["text"].setText(str(stats["by_kind"]["text"]))
        self.stat_labels["file"].setText(str(stats["by_kind"]["file"]))
        for item in self.vault.search(self.search_box.text()):
            display = f'[{item["kind"].upper()}]  {item["title"]}    ·    {item["created_at"][:16]}'
            widget_item = QListWidgetItem(display)
            widget_item.setData(Qt.ItemDataRole.UserRole, item["id"])
            self.items.addItem(widget_item)
            if selected_id == item["id"]:
                self.items.setCurrentItem(widget_item)
        if self.items.currentItem() is None and self.items.count():
            self.items.setCurrentRow(0)
        elif self.items.currentItem() is None:
            self.show_details(None, None)

    def show_details(self, current: QListWidgetItem | None, *_: object) -> None:
        item = self.vault.get(current.data(Qt.ItemDataRole.UserRole)) if current else None
        if not item:
            self.detail_title.setText("Your memories")
            self.detail_meta.setText("Choose an item from the archive")
            self.detail_body.setText("A private collection, stored locally on this device.")
            self.preview.setPixmap(QPixmap())
            self.preview.setText("Select a memory to inspect it")
            return

        self.detail_title.setText(item["title"])
        self.detail_meta.setText(f'{item["kind"].upper()}  ·  {item["created_at"][:19].replace("T", " ")}\nSource: {item["source"]}')
        if item["kind"] in ("text", "url"):
            content = item["content"]
            self.detail_body.setText(content[:4000] + ("\n… preview truncated" if len(content) > 4000 else ""))
        else:
            self.detail_body.setText(f'Original name: {item.get("original_name") or item["title"]}\nStored in your local Cerberus archive.')
        self.preview.setPixmap(QPixmap())
        self.preview.setText("MEMORY PREVIEW" if item["kind"] in ("text", "url") else "FILE ATTACHMENT  ·  OPEN MANUALLY")
        stored = item.get("stored_path")
        if item["kind"] == "file" and stored:
            path = Path(stored)
            in_vault = path.resolve().is_relative_to(self.vault.files_dir.resolve())
            if in_vault and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"} and path.is_file():
                reader = QImageReader(str(path))
                dimensions = reader.size()
                if dimensions.isValid() and dimensions.width() * dimensions.height() <= 16_000_000:
                    target = QSize(self.preview.width() - 20, 190)
                    scaled = dimensions.scaled(target, Qt.AspectRatioMode.KeepAspectRatio)
                    reader.setScaledSize(scaled)
                    image = reader.read()
                    if not image.isNull():
                        self.preview.setPixmap(QPixmap.fromImage(image).scaled(
                            self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation))
                        self.preview.setText("")

    def export_archive(self, *_: object) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Cerberus archive", "cerberus-export.json", "JSON files (*.json)")
        if not path:
            return
        try:
            self.vault.export_json(path)
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Archive exported", "Archive metadata and text were exported. Attached file bytes remain in the local vault.")

    def copy_selected(self, *_: object) -> None:
        item = self.selected()
        if item and item["kind"] in ("text", "url"):
            QApplication.clipboard().setText(item["content"])

    def open_selected(self, *_: object) -> None:
        item = self.selected()
        if item and item["kind"] == "file" and item["stored_path"]:
            path = Path(item["stored_path"])
            if path.is_file():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def delete_selected(self, *_: object) -> None:
        item = self.selected()
        if item is None:
            return
        answer = QMessageBox.question(self, "Delete memory",
            f'Delete "{item["title"]}" from the Cerberus vault?')
        if answer == QMessageBox.StandardButton.Yes:
            self.vault.delete(item["id"])
            self.refresh()


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
        self.window = VaultWindow(self.vault)
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
        self.pet.came_back.connect(self.pet_came_back)
        self.dock = ReturnButton(self.pet._sprite)
        self.dock.clicked.connect(self.summon_pet)
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
        if self.settings.show_pet:
            self.pet.show()
            QTimer.singleShot(1200, self.pet.greet)
        if self._storage_warning:
            QTimer.singleShot(1500, lambda: self.pet.tell(self._storage_warning, seconds=6))
        self.app.setQuitOnLastWindowClosed(False)

    def _language(self) -> str:
        return resolve_language(self.settings.language, QLocale.system().name())

    def shutdown(self) -> None:
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
        if (self.settings.shortcut_action == "toggle" and self.pet.isVisible()
                and not self.pet.is_away):
            self.send_away()
        else:
            self.summon_pet()

    # ----- presence --------------------------------------------------------
    def summon_pet(self, *_: object) -> None:
        """Bring Cerberus to the mouse cursor through the portal."""
        if not self.settings.show_pet:
            self.settings.show_pet = True
            self.settings.save(self.home)
        self.dock.hide()
        was_away = self.pet.is_away or not self.pet.isVisible()
        self.pet.arrive(self.pet.quips.pick("arrive") if was_away else "")

    def send_away(self, *_: object) -> None:
        self.pet.dismiss()

    def pet_went_away(self, side: int, bottom_y: int) -> None:
        if self.settings.show_return_button:
            self.dock.show_at(side, bottom_y, self.pet.screen())

    def pet_came_back(self) -> None:
        self.dock.hide()

    def tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_pet()

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
        if self.pet.is_away:
            self.summon_pet()
            return
        visible = not self.pet.isVisible()
        self.pet.setVisible(visible)
        if not visible:
            self.dock.hide()
        self.settings.show_pet = visible
        self.settings.save(self.home)

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

    def change_storage(self, folder: Path, *, copy_existing: bool) -> None:
        """Point the vault at another folder, optionally copying current memories."""
        folder = Path(folder).resolve()
        if copy_existing and not Vault.has_vault(folder):
            self.vault.copy_to(folder)
        new_vault = Vault(folder)
        old = self.vault
        self.vault = new_vault
        self.window.vault = new_vault
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
            self.dock.hide()
            self.pet.summon(message, carry)
            if self.window.isVisible():
                self.window.refresh()
        except (CaptureError, OSError, ValueError) as exc:
            self.pet.tell(f'{quips.pick("error")} ({exc})'[:90])
            QMessageBox.warning(self.window, "Cerberus — Capture error", str(exc))


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
