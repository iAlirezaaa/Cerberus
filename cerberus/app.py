"""Desktop controller, system tray, clipboard opt-in and search UI."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QImageReader, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMenu, QMessageBox, QPushButton, QSystemTrayIcon,
    QVBoxLayout, QWidget,
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
        self.vault = Vault(self.home)
        self.window = VaultWindow(self.vault)
        self.pet = CerberusPet(
            reduced_motion=self.settings.reduced_motion,
            standby_seconds=self.settings.standby_seconds,
        )
        self.pet.set_pet_size(self.settings.pet_size)
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
        self.menu.addAction("Summon / wake Cerberus", lambda: self.pet.play("wake"))
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

    def set_pet_size(self, size: int) -> None:
        self.pet.set_pet_size(size)
        self.settings.pet_size = self.pet.width()
        self.settings.save(self.home)

    def set_reduced_motion(self, enabled: bool) -> None:
        self.settings.reduced_motion = enabled
        self.pet.set_reduced_motion(enabled)
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
