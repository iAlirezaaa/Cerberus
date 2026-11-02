"""Desktop controller, system tray, clipboard opt-in and search UI."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QMessageBox, QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from .pet import CerberusPet, mime_image_png
from .settings import Settings, data_dir
from .vault import CaptureError, Vault


def tray_icon() -> QIcon:
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
        self.setWindowTitle("Cerberus — Memory Vault")
        self.resize(640, 470)
        self.setStyleSheet("""
            QWidget { background: #121d25; color: #e8e5dc; font-size: 13px; }
            QLineEdit, QListWidget { background: #1b2b33; border: 1px solid #34515a;
              border-radius: 8px; padding: 9px; }
            QPushButton { background: #255759; border-radius: 8px; padding: 9px 14px; }
            QPushButton:hover { background: #327579; }
        """)
        layout = QVBoxLayout(self)
        header = QLabel("CERBERUS  /  THE VAULT")
        header.setStyleSheet("color: #f0b36b; font-weight: bold; font-size: 19px;")
        layout.addWidget(header)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search your saved memories…")
        self.search_box.textChanged.connect(self.refresh)
        layout.addWidget(self.search_box)
        self.items = QListWidget()
        self.items.itemDoubleClicked.connect(self.open_selected)
        layout.addWidget(self.items, 1)
        row = QHBoxLayout()
        for label, callback in [
            ("Copy text / URL", self.copy_selected),
            ("Open saved file", self.open_selected),
            ("Delete", self.delete_selected),
            ("Refresh", self.refresh),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        self.refresh()

    def selected(self) -> dict | None:
        item = self.items.currentItem()
        return self.vault.get(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def refresh(self, *_: object) -> None:
        selected = self.selected()
        selected_id = selected["id"] if selected else None
        self.items.clear()
        for item in self.vault.search(self.search_box.text()):
            display = f'[{item["kind"].upper()}]  {item["title"]}    ·    {item["created_at"][:16]}'
            widget_item = QListWidgetItem(display)
            widget_item.setData(Qt.ItemDataRole.UserRole, item["id"])
            self.items.addItem(widget_item)
            if selected_id == item["id"]:
                self.items.setCurrentItem(widget_item)

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
        self.vault = Vault(self.home)
        self.window = VaultWindow(self.vault)
        self.pet = CerberusPet(reduced_motion=self.settings.reduced_motion)
        self.pet.capture_requested.connect(self.capture)
        self.pet.vault_requested.connect(self.open_vault)
        self.pet.menu_requested.connect(self.open_menu)
        self.tray = QSystemTrayIcon(tray_icon(), app)
        self.tray.setToolTip("Cerberus — your memory guardian")
        self.menu = QMenu()
        show = self.menu.addAction("Show / hide Cerberus")
        show.triggered.connect(self.toggle_pet)
        self.menu.addAction("Open memory vault", self.open_vault)
        self.menu.addAction("Feed current clipboard", self.feed_clipboard)
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
        self.app.clipboard().dataChanged.connect(self.clipboard_changed)
        self.app.aboutToQuit.connect(self.vault.close)
        if self.settings.show_pet:
            self.pet.show()
        self.app.setQuitOnLastWindowClosed(False)

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

    def toggle_pet(self, *_: object) -> None:
        visible = not self.pet.isVisible()
        self.pet.setVisible(visible)
        self.settings.show_pet = visible
        self.settings.save(self.home)

    def set_clipboard(self, enabled: bool) -> None:
        self.settings.clipboard_capture = enabled
        self.settings.save(self.home)
        self.pet.tell("Clipboard capture ON" if enabled else "Clipboard capture OFF")

    def set_reduced_motion(self, enabled: bool) -> None:
        self.settings.reduced_motion = enabled
        self.pet.reduced_motion = enabled
        self.settings.save(self.home)

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
        try:
            if kind == "files":
                paths = list(value)
                if not paths:
                    return
                for path in paths:
                    self.vault.add_file(Path(path), source="drop-or-clipboard")
                message = f"Guarded {len(paths)} file(s)!"
            elif kind == "text":
                item = self.vault.capture_text(str(value), source="drop-or-clipboard")
                message = f'Guarded {item["kind"]}!'
            elif kind == "image":
                self.vault.add_bytes(bytes(value), name="captured-image.png", source="drop-or-clipboard")
                message = "Image guarded!"
            else:
                return
            self.pet.summon(message)
            if self.window.isVisible():
                self.window.refresh()
        except (CaptureError, OSError, ValueError) as exc:
            self.pet.tell(f"Couldn't capture: {exc}")
            QMessageBox.warning(self.window, "Cerberus — Capture error", str(exc))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Cerberus")
    app.setQuitOnLastWindowClosed(False)
    controller = Controller(app)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
