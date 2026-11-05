"""Item-kind icons: designed art from cerberus/assets/icons, or a drawn ember fallback."""
from __future__ import annotations

from importlib import resources
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap

from .item_kinds import KINDS

_LABELS = {
    "text": "Aa", "link": "www", "image": "IMG", "pdf": "PDF", "document": "DOC",
    "spreadsheet": "XLS", "presentation": "PPT", "archive": "ZIP", "code": "</>",
    "audio": "♪", "video": "▶", "app": "APP", "font": "Ff", "email": "@",
    "model3d": "3D", "file": "•••",
}
_cache: dict[tuple[str, int], QPixmap] = {}
MAX_ICON_BYTES = 2 * 1024 * 1024


def _asset(name: str) -> bytes | None:
    try:
        node = resources.files("cerberus").joinpath("assets", "icons", name)
        if not node.is_file():
            return None
        data = node.read_bytes()
        return data if len(data) <= MAX_ICON_BYTES else None
    except (OSError, ValueError):
        return None


def animated_icon_path(kind: str) -> Path | None:
    """Path of the designed animated GIF for a kind, if bundled."""
    if kind not in KINDS:
        return None
    try:
        node = resources.files("cerberus").joinpath("assets", "icons", f"{kind}.gif")
        path = Path(str(node))
        return path if path.is_file() and path.stat().st_size <= MAX_ICON_BYTES else None
    except (OSError, ValueError, TypeError):
        return None


def _drawn(kind: str, size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 128
    card = QRectF(22 * s, 10 * s, 84 * s, 108 * s)
    gradient = QLinearGradient(card.topLeft(), card.bottomRight())
    gradient.setColorAt(0, QColor("#ffe29a"))
    gradient.setColorAt(1, QColor("#ff8a2a"))
    p.setPen(QPen(QColor("#5a2010"), max(1.0, 3 * s)))
    p.setBrush(gradient)
    p.drawRoundedRect(card, 12 * s, 12 * s)
    fold = QRectF(card.right() - 24 * s, card.top(), 24 * s, 24 * s)
    p.setBrush(QColor(255, 246, 220, 200))
    p.drawRoundedRect(fold, 6 * s, 6 * s)
    font = QFont()
    font.setFamilies(["Segoe UI", "Arial"])
    font.setBold(True)
    label = _LABELS.get(kind, "•••")
    font.setPixelSize(max(6, int((34 if len(label) <= 2 else 26) * s)))
    p.setFont(font)
    p.setPen(QColor("#6b2410"))
    p.drawText(card.adjusted(0, 18 * s, 0, 0), Qt.AlignmentFlag.AlignCenter, label)
    p.end()
    return pixmap


def kind_icon(kind: str, size: int = 32) -> QPixmap:
    """Static icon for an item kind at the requested size (cached)."""
    kind = kind if kind in KINDS else "file"
    key = (kind, size)
    if key not in _cache:
        pixmap = QPixmap()
        data = _asset(f"{kind}.png")
        if data is None or not pixmap.loadFromData(QByteArray(data), "PNG") or pixmap.isNull():
            pixmap = _drawn(kind, max(size, 64))
        _cache[key] = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
    return _cache[key]


def has_designed_icon(kind: str) -> bool:
    return _asset(f"{kind}.png") is not None
