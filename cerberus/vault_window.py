"""The memory archive window: search, rich previews and the storage location."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QImageReader, QMovie, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget,
)

from .icons import animated_icon_path, kind_icon
from .item_kinds import (
    clean_text, decode_text, human_size, is_runnable, kind_for, preview_for_content,
    preview_mode, sniff,
)
from .vault import Vault

MAX_PREVIEW_PIXELS = 40_000_000
MAX_TEXT_PREVIEW_BYTES = 64 * 1024
MAX_TEXT_CHARS = 20_000
# Files are read into memory for previews, so Windows never sees an open handle
# (delete / move keep working while something is previewed).
MAX_PREVIEW_BYTES = 50 * 1024 * 1024
MAX_MOVIE_FRAMES = 400
ALLOCATION_LIMIT_MB = 256
_FORMATS = {"png": b"png", "jpeg": b"jpeg", "gif": b"gif", "webp": b"webp", "bmp": b"bmp"}

try:  # QtPdf ships with PySide6 wheels; tolerate builds without it.
    from PySide6.QtPdf import QPdfDocument
except ImportError:  # pragma: no cover - depends on the PySide6 build
    QPdfDocument = None

STYLE = """
    QWidget { background: #100d11; color: #eee7df; font-size: 13px; }
    QLabel#eyebrow { color: #f08a55; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
    QLabel#title { color: #fff2df; font-size: 26px; font-weight: 700; }
    QLabel#muted { color: #a99b98; }
    QLabel#location { background: #171319; border: 1px solid #3a2930; border-radius: 8px;
                      padding: 6px 10px; color: #ffd5a2; font-family: Consolas, monospace; }
    QFrame#statCard, QFrame#detailCard { background: #19151b; border: 1px solid #3a2930; border-radius: 12px; }
    QLabel#statValue { color: #ffc27c; font-size: 22px; font-weight: 700; }
    QLabel#statLabel { color: #b8a8a1; font-size: 11px; }
    QLineEdit, QListWidget, QTextEdit, QPlainTextEdit { background: #171319; border: 1px solid #49333a;
      border-radius: 9px; padding: 10px; selection-background-color: #6e342d; }
    QPlainTextEdit#code { font-family: Consolas, "Cascadia Mono", monospace; font-size: 12px; }
    QListWidget::item { padding: 8px 6px; border-bottom: 1px solid #2a2028; }
    QListWidget::item:selected { background: #302027; border-radius: 6px; color: #ffd5a2; }
    QPushButton { background: #592d2a; border: 1px solid #a34e38; border-radius: 8px; padding: 8px 13px; }
    QPushButton:hover { background: #793d30; }
    QPushButton#secondary { background: #211a22; border-color: #4b3741; }
    QPushButton#secondary:hover { background: #33232b; }
"""


def safe_vault_file(vault: Vault, stored: str | None) -> Path | None:
    """A stored file path, only if it is a regular file inside this vault's files folder."""
    if not stored:
        return None
    path = Path(stored)
    try:
        if path.is_symlink() or not path.is_file():
            return None
        resolved = path.resolve()
        if not resolved.is_relative_to(vault.files_dir.resolve()):
            return None
        return resolved
    except OSError:
        return None


class VaultWindow(QWidget):
    def __init__(self, vault: Vault, *,
                 change_storage: Callable[[QWidget], None] | None = None) -> None:
        super().__init__()
        self.vault = vault
        self.change_storage_cb = change_storage
        self._movie: QMovie | None = None
        self._pdf = None
        self._buffer: QBuffer | None = None
        self.setWindowTitle("Cerberus — Memory Archive")
        self.resize(980, 680)
        self.setMinimumSize(760, 520)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)
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

        location_row = QHBoxLayout()
        location_row.addWidget(QLabel("Stored in:"))
        self.location = QLabel()
        self.location.setObjectName("location")
        self.location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.location.setTextFormat(Qt.TextFormat.PlainText)
        location_row.addWidget(self.location, 1)
        open_folder = QPushButton("Open folder")
        open_folder.setObjectName("secondary")
        open_folder.clicked.connect(self.open_folder)
        location_row.addWidget(open_folder)
        self.change_button = QPushButton("Change…")
        self.change_button.clicked.connect(self.change_location)
        location_row.addWidget(self.change_button)
        layout.addLayout(location_row)

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
        self.items.setIconSize(QSize(30, 30))
        self.items.itemDoubleClicked.connect(self.open_selected)
        # Arrowing through the list waits a moment before decoding a preview.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(120)
        self._debounce.timeout.connect(
            lambda: self.isVisible() and self.show_details(self.items.currentItem()))
        self.items.currentItemChanged.connect(lambda *_: self._debounce.start())
        content_row.addWidget(self.items, 3)
        detail = QFrame()
        detail.setObjectName("detailCard")
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(16, 16, 16, 16)
        self.stack = QStackedWidget()
        self.stack.setMinimumHeight(220)
        self.preview = QLabel("Select a memory to inspect it")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background:#110e13; border-radius:9px; color:#8e7c7c; padding:10px;")
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.TextFormat.PlainText)
        self.text_view = QPlainTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setObjectName("code")
        self.stack.addWidget(self.preview)
        self.stack.addWidget(self.text_view)
        self.detail_title = QLabel("Your memories")
        self.detail_title.setWordWrap(True)
        self.detail_title.setStyleSheet("font-size:17px;font-weight:700;color:#ffe3bf;")
        self.detail_title.setTextFormat(Qt.TextFormat.PlainText)
        self.detail_meta = QLabel("Choose an item from the archive")
        self.detail_meta.setObjectName("muted")
        self.detail_meta.setWordWrap(True)
        self.detail_meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail_meta.setTextFormat(Qt.TextFormat.PlainText)
        self.open_link_button = QPushButton("Open link in browser")
        self.open_link_button.setObjectName("secondary")
        self.open_link_button.clicked.connect(self.open_link)
        self.open_link_button.hide()
        detail_layout.addWidget(self.stack, 4)
        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_meta)
        detail_layout.addWidget(self.open_link_button, 0, Qt.AlignmentFlag.AlignLeft)
        content_row.addWidget(detail, 3)
        layout.addLayout(content_row, 1)

        row = QHBoxLayout()
        for label, callback in [
            ("Copy text / URL", self.copy_selected),
            ("Open saved file", self.open_selected),
            ("Show in folder", self.reveal_selected),
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

    # ----- data ------------------------------------------------------------
    def set_vault(self, vault: Vault) -> None:
        self._release_preview()
        self.vault = vault
        self.refresh()

    def selected(self) -> dict | None:
        item = self.items.currentItem()
        return self.vault.get(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def refresh(self, *_: object) -> None:
        self.location.setText(str(self.vault.home.resolve()))
        self.change_button.setEnabled(self.change_storage_cb is not None)
        selected = self.selected()
        selected_id = selected["id"] if selected else None
        self.items.blockSignals(True)
        self.items.clear()
        stats = self.vault.stats()
        self.stat_labels["total"].setText(str(stats["total"]))
        self.stat_labels["text"].setText(str(stats["by_kind"]["text"]))
        self.stat_labels["file"].setText(str(stats["by_kind"]["file"]))
        current = None
        for item in self.vault.search(self.search_box.text()):
            display = f'{item["title"]}\n{item["kind"].upper()}  ·  {item["created_at"][:16].replace("T", " ")}'
            widget_item = QListWidgetItem(QIcon(kind_icon(kind_for(item), 30)), display)
            widget_item.setData(Qt.ItemDataRole.UserRole, item["id"])
            self.items.addItem(widget_item)
            if selected_id == item["id"]:
                current = widget_item
        self.items.blockSignals(False)
        if current is not None:
            self.items.setCurrentItem(current)
        elif self.items.count():
            self.items.setCurrentRow(0)
        self.show_details(self.items.currentItem())

    # ----- preview ---------------------------------------------------------
    def _release_preview(self) -> None:
        if self._movie is not None:
            self._movie.stop()
            self.preview.setMovie(None)
            self._movie.deleteLater()
            self._movie = None
        if self._pdf is not None:
            self._pdf.close()
            self._pdf.deleteLater()
            self._pdf = None
        if self._buffer is not None:
            self._buffer.close()
            self._buffer = None
        self.preview.setPixmap(QPixmap())
        self.preview.setText("")

    @staticmethod
    def _read(path: Path, limit: int = MAX_PREVIEW_BYTES) -> bytes | None:
        try:
            if path.stat().st_size > limit:
                return None
            return path.read_bytes()
        except OSError:
            return None

    def _device(self, data: bytes) -> QBuffer:
        """In-memory device that lives as long as the current preview."""
        buffer = QBuffer()
        buffer.setData(QByteArray(data))
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self._buffer = buffer
        return buffer

    def _box(self) -> QSize:
        return QSize(max(160, self.stack.width() - 24), max(160, self.stack.height() - 24))

    def _show_message(self, text: str) -> None:
        self.stack.setCurrentWidget(self.preview)
        self.preview.setText(text)

    def _show_pixmap(self, pixmap: QPixmap) -> None:
        self.stack.setCurrentWidget(self.preview)
        box = self._box()
        if pixmap.width() > box.width() or pixmap.height() > box.height():
            pixmap = pixmap.scaled(box, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
        self.preview.setText("")
        self.preview.setPixmap(pixmap)

    def _show_movie(self, data: bytes, fmt: str, *, fit: bool = True) -> bool:
        probe = QBuffer()
        probe.setData(QByteArray(data))
        probe.open(QIODevice.OpenModeFlag.ReadOnly)
        reader = QImageReader(probe, _FORMATS[fmt])
        reader.setDecideFormatFromContent(False)
        size = reader.size()
        frames = reader.imageCount()
        probe.close()
        if (not size.isValid() or size.width() * size.height() > MAX_PREVIEW_PIXELS
                or frames > MAX_MOVIE_FRAMES
                or frames * size.width() * size.height() > 4 * MAX_PREVIEW_PIXELS):
            return False
        movie = QMovie(self._device(data), _FORMATS[fmt], self)
        if not movie.isValid():
            return False
        box = self._box()
        if fit and (size.width() > box.width() or size.height() > box.height()):
            movie.setScaledSize(size.scaled(box, Qt.AspectRatioMode.KeepAspectRatio))
        self._movie = movie
        self.stack.setCurrentWidget(self.preview)
        self.preview.setText("")
        self.preview.setMovie(movie)
        if self.isVisible():
            movie.start()
        else:
            movie.jumpToFrame(0)
        return True

    def _image(self, data: bytes, fmt: str) -> QPixmap | None:
        buffer = QBuffer()
        buffer.setData(QByteArray(data))
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        reader = QImageReader(buffer, _FORMATS[fmt])
        reader.setDecideFormatFromContent(False)
        if hasattr(reader, "setAllocationLimit"):
            reader.setAllocationLimit(ALLOCATION_LIMIT_MB)
        size = reader.size()
        if not size.isValid() or size.width() * size.height() > MAX_PREVIEW_PIXELS:
            return None
        box = self._box()
        if size.width() > box.width() or size.height() > box.height():
            reader.setScaledSize(size.scaled(box, Qt.AspectRatioMode.KeepAspectRatio))
        image = reader.read()
        buffer.close()
        return None if image.isNull() else QPixmap.fromImage(image)

    def _pdf_page(self, data: bytes) -> tuple[QPixmap | None, int, str]:
        """Render page 1 from memory. Returns (image, page count, problem)."""
        if QPdfDocument is None:
            return None, 0, "PDF preview isn't available in this build."
        document = QPdfDocument(self)
        self._pdf = document
        document.load(self._device(data))
        status = document.error()
        if status == QPdfDocument.Error.IncorrectPassword:
            return None, 0, "This PDF is password-protected."
        if status != QPdfDocument.Error.None_ or document.pageCount() < 1:
            return None, 0, "This PDF couldn't be read."
        point = document.pagePointSize(0)
        if point.width() <= 0 or point.height() <= 0:
            return None, document.pageCount(), "Page 1 has no size."
        target = point.toSize().scaled(self._box(), Qt.AspectRatioMode.KeepAspectRatio)
        image = document.render(0, target)
        if image.isNull():
            return None, document.pageCount(), "Page 1 couldn't be drawn."
        # PDF pages render with a transparent background; put them on paper.
        page = QPixmap(image.size())
        page.fill(QColor("white"))
        painter = QPainter(page)
        painter.drawImage(0, 0, image)
        painter.end()
        return page, document.pageCount(), ""

    def _text_head(self, path: Path) -> str | None:
        try:
            with path.open("rb") as handle:  # closed straight away; only the head is read
                data = handle.read(MAX_TEXT_PREVIEW_BYTES + 1)
        except OSError:
            return None
        text = decode_text(data[:MAX_TEXT_PREVIEW_BYTES])
        if text is not None and len(data) > MAX_TEXT_PREVIEW_BYTES:
            text += "\n\n… preview shows the first 64 KB"
        return text

    def _icon_preview(self, kind: str) -> None:
        gif = animated_icon_path(kind)
        data = self._read(gif, limit=2 * 1024 * 1024) if gif is not None else None
        if data is None or not self._show_movie(data, "gif", fit=False):
            self._show_pixmap(kind_icon(kind, 128))

    def show_details(self, current: QListWidgetItem | None, *_: object) -> None:
        self._release_preview()
        self.open_link_button.hide()
        item = self.vault.get(current.data(Qt.ItemDataRole.UserRole)) if current else None
        if not item:
            self.detail_title.setText("Your memories")
            self.detail_meta.setText("Choose an item from the archive")
            self._show_message("Select a memory to inspect it")
            return
        kind = kind_for(item)
        mode = preview_mode(item)
        self.detail_title.setText(item["title"])
        meta = [f'{kind.upper()}  ·  {item["created_at"][:19].replace("T", " ")}',
                f'Source: {item["source"]}']
        path = safe_vault_file(self.vault, item.get("stored_path"))
        if item["kind"] == "file":
            if path is not None:
                meta.append(f"{human_size(path.stat().st_size)}  ·  original name: "
                            f'{item.get("original_name") or item["title"]}')
            else:
                meta.append("Stored copy is missing from the vault folder.")
        data = None
        if mode != "text" and path is not None and mode != "text_file":
            data = self._read(path)
            if data is not None:
                mode = preview_for_content(mode, data[:16])
            else:
                mode = "icon_only"
        fmt = None
        if data is not None:
            fmt = sniff(data[:16])
        if mode == "text":
            content = clean_text(item["content"])
            self.text_view.setPlainText(content[:MAX_TEXT_CHARS] + (
                "\n\n… preview truncated" if len(content) > MAX_TEXT_CHARS else ""))
            self.stack.setCurrentWidget(self.text_view)
            if item["kind"] == "url":
                self.open_link_button.show()
        elif path is None:
            self._icon_preview(kind)
        elif mode == "animated_image" and fmt in ("gif", "webp"):
            if not self._show_movie(data, fmt):
                pixmap = self._image(data, fmt)
                self._show_pixmap(pixmap) if pixmap else self._icon_preview(kind)
        elif mode == "image" and fmt in _FORMATS:
            pixmap = self._image(data, fmt)
            self._show_pixmap(pixmap) if pixmap else self._icon_preview(kind)
        elif mode == "pdf":
            pixmap, pages, problem = self._pdf_page(data)
            if pages:
                meta.append(f"{pages} page{'s' if pages != 1 else ''} · showing page 1")
            if problem:
                meta.append(problem)
            self._show_pixmap(pixmap) if pixmap else self._icon_preview(kind)
        elif mode == "text_file":
            text = self._text_head(path)
            if text is None:
                self._icon_preview(kind)
            else:
                self.text_view.setPlainText(text)
                self.stack.setCurrentWidget(self.text_view)
        else:
            self._icon_preview(kind)
        self.detail_meta.setText("\n".join(meta))

    # ----- actions ---------------------------------------------------------
    def open_folder(self, *_: object) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.vault.home)))

    def change_location(self, *_: object) -> None:
        if self.change_storage_cb is not None:
            self.change_storage_cb(self)

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

    def open_link(self, *_: object) -> None:
        item = self.selected()
        if not item or item["kind"] != "url":
            return
        url = QUrl(item["content"].strip())
        if url.scheme() not in ("http", "https") or not url.host():
            QMessageBox.information(self, "Not opened", "Only http and https links are opened.")
            return
        answer = QMessageBox.question(self, "Open link?",
                                      f"Open this page in your browser?\n\n{url.host()}")
        if answer == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(url)

    def open_selected(self, *_: object) -> None:
        item = self.selected()
        if item and item["kind"] == "file":
            path = safe_vault_file(self.vault, item.get("stored_path"))
            if path is None:
                return
            if is_runnable(item):
                QMessageBox.information(
                    self, "Not opened",
                    "Cerberus never runs programs or scripts. The stored copy is shown in its "
                    "folder instead.")
                self.reveal_selected()
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        elif item and item["kind"] == "url":
            self.open_link()

    def reveal_selected(self, *_: object) -> None:
        item = self.selected()
        path = safe_vault_file(self.vault, item.get("stored_path")) if item else None
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent if path else self.vault.home)))

    def delete_selected(self, *_: object) -> None:
        item = self.selected()
        if item is None:
            return
        answer = QMessageBox.question(self, "Delete memory",
            f'Delete "{item["title"]}" from the Cerberus vault?')
        if answer == QMessageBox.StandardButton.Yes:
            self._release_preview()
            self.vault.delete(item["id"])
            self.refresh()

    def hideEvent(self, event) -> None:
        self._debounce.stop()
        if self._movie is not None:
            self._movie.setPaused(True)
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        if self._movie is not None:
            self._movie.setPaused(False)
            self._movie.start()
        super().showEvent(event)

    def closeEvent(self, event) -> None:
        self._release_preview()
        super().closeEvent(event)
