"""Transparent animated Cerberus mascot for the user's actual desktop.

The illustration is an original SVG sprite bundled with the package. A small
state machine moves and scales it instead of re-rendering the vector every frame.
"""
from __future__ import annotations

import math
import time
from importlib import resources

from PySide6.QtCore import QByteArray, QPoint, QRectF, Qt, QTimer, QBuffer, QIODevice, Signal
from PySide6.QtGui import QColor, QCursor, QImage, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget

from .motion import MotionMachine

BASE_WIDTH = 340
BASE_HEIGHT = 310


def mime_image_png(mime) -> bytes | None:
    """Convert a dropped Qt image to PNG data without touching the disk."""
    if not mime.hasImage():
        return None
    image = mime.imageData()
    if hasattr(image, "toImage"):
        image = image.toImage()
    if not isinstance(image, QImage) or image.isNull():
        return None
    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        return None
    if not image.save(buffer, "PNG"):
        return None
    return bytes(buffer.data())


def _sprite_pixmap() -> QPixmap:
    """Rasterize the high-resolution transparent vector only once."""
    raw = resources.files("cerberus").joinpath("assets/guardian.svg").read_bytes()
    renderer = QSvgRenderer(QByteArray(raw))
    if not renderer.isValid():
        raise RuntimeError("Cerberus's guardian.svg character asset is invalid")
    pixmap = QPixmap(720, 600)
    pixmap.fill(Qt.GlobalColor.transparent)
    with_painter = QPainter(pixmap)
    with_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(with_painter, QRectF(0, 0, 720, 600))
    with_painter.end()
    return pixmap


class CerberusPet(QWidget):
    capture_requested = Signal(str, object)
    vault_requested = Signal()
    menu_requested = Signal(QPoint)

    def __init__(self, *, reduced_motion: bool = False,
                 standby_seconds: float = 95.0) -> None:
        super().__init__()
        self.setWindowTitle("Cerberus — the guardian")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setToolTip("Cerberus — drop text, links, images or files here; double-click to search.")
        self.reduced_motion = reduced_motion
        self.motion = MotionMachine(
            standby_after=standby_seconds, reduced_motion=reduced_motion
        )
        self._sprite = _sprite_pixmap()
        self._size = BASE_WIDTH
        self.setFixedSize(BASE_WIDTH, BASE_HEIGHT)
        self._drag_offset: QPoint | None = None
        self._press_position: QPoint | None = None
        self._dragged = False
        self._message = "Feed me something!"
        self._message_until = time.monotonic() + 4
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(180)
        self._timer.start()
        self.place_at_screen_corner()

    @property
    def _phase(self) -> str:
        """Legacy public-ish state used by the original GUI smoke test."""
        return self.motion.phase

    def place_at_screen_corner(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is not None:
            g = screen.availableGeometry()
            self.move(
                max(g.left(), g.right() - self.width() - 22),
                max(g.top(), g.bottom() - self.height() - 12),
            )

    def _on_screen(self, x: int, y: int) -> QPoint:
        target = QPoint(x + self.width() // 2, y + self.height() // 2)
        screen = QApplication.screenAt(target) or QApplication.primaryScreen()
        if screen is None:
            return QPoint(x, y)
        area = screen.availableGeometry()
        return QPoint(
            max(area.left(), min(x, area.right() - self.width() + 1)),
            max(area.top(), min(y, area.bottom() - self.height() + 1)),
        )

    def set_pet_size(self, width: int) -> None:
        """Small/medium/large sizes preserve aspect ratio and visible position."""
        width = max(180, min(500, int(width)))
        origin = self.pos()
        self._size = width
        self.setFixedSize(width, round(BASE_HEIGHT * width / BASE_WIDTH))
        self.move(self._on_screen(origin.x(), origin.y()))
        self.update()

    def set_reduced_motion(self, enabled: bool) -> None:
        self.reduced_motion = enabled
        self.motion.reduced_motion = enabled
        self.update()

    def tell(self, message: str, *, seconds: float = 2.8) -> None:
        self._message = message[:64]
        self._message_until = time.monotonic() + seconds
        self.update()

    def summon(self, message: str = "Caught!") -> None:
        """Summon from the portal at the current mouse position after capture."""
        cursor = QCursor.pos()
        self.move(self._on_screen(cursor.x() - self.width() // 2,
                                  cursor.y() - self.height() // 2))
        self.motion.capture()
        self.tell(message)
        self.show()
        self.raise_()
        self._tick()

    def play(self, action: str = "play") -> None:
        if action not in ("play", "alert", "wake", "sleep", "guard", "idle"):
            raise ValueError("Invalid pet action")
        self.motion.transition(action)
        if action == "sleep":
            self.tell("Zzz…", seconds=2)
        elif action == "guard":
            self.tell("Guard mode", seconds=2)
        elif action == "play":
            self.tell("Woof!", seconds=1)
        self.show()
        self._tick()

    def _tick(self) -> None:
        now = time.monotonic()
        self.motion.update(now=now)
        if self._phase in ("sleep", "guard"):
            target_interval = 900
        elif self._phase == "idle":
            target_interval = 140 if not self.reduced_motion else 500
        else:
            target_interval = 33 if not self.reduced_motion else 200
        if self._timer.interval() != target_interval:
            self._timer.setInterval(target_interval)
        self.update()

    def dragEnterEvent(self, event) -> None:
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasText() or mime.hasImage():
            event.acceptProposedAction()
            self.play("alert")

    def dragMoveEvent(self, event) -> None:
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasText() or mime.hasImage():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        mime = event.mimeData()
        captured = False
        if mime.hasUrls():
            files = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
            links = [u.toString() for u in mime.urls() if not u.isLocalFile()]
            if files:
                self.capture_requested.emit("files", files)
                captured = True
            for link in links:
                self.capture_requested.emit("text", link)
                captured = True
        elif mime.hasText():
            self.capture_requested.emit("text", mime.text())
            captured = True
        elif mime.hasImage():
            png = mime_image_png(mime)
            if png is not None:
                self.capture_requested.emit("image", png)
                captured = True
        if captured:
            event.acceptProposedAction()

    def enterEvent(self, event) -> None:
        if self._phase == "sleep":
            self.motion.transition("wake")
            self._tick()
        super().enterEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.globalPosition().toPoint()
            self._drag_offset = self._press_position - self.frameGeometry().topLeft()
            self._dragged = False
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            point = event.globalPosition().toPoint()
            if self._press_position is not None and (point - self._press_position).manhattanLength() >= 6:
                self._dragged = True
            if self._dragged:
                desired = point - self._drag_offset
                self.move(self._on_screen(desired.x(), desired.y()))
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self._dragged:
            self.motion.touch()
            self.tell("Good human!", seconds=1.2)
            self._tick()
        self._drag_offset = None
        self._press_position = None
        self._dragged = False

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.vault_requested.emit()
            event.accept()

    def contextMenuEvent(self, event) -> None:
        self.menu_requested.emit(event.globalPos())

    def _portal(self, painter: QPainter, progress: float) -> None:
        painter.save()
        opacity = max(0.05, 1.0 - progress * .75)
        painter.setOpacity(opacity)
        painter.translate(155, 158)
        painter.rotate(190 * progress)
        painter.setBrush(QColor("#30221e"))
        painter.setPen(QPen(QColor("#ee703c"), 7))
        painter.drawEllipse(QRectF(-92, -90, 184, 180))
        painter.setPen(QPen(QColor("#ffbf6b"), 2))
        painter.drawEllipse(QRectF(-82, -80, 164, 160))
        painter.setPen(QPen(QColor("#32bcb2"), 5))
        painter.drawArc(QRectF(-101, -97, 202, 194), 15 * 16, 155 * 16)
        painter.setPen(QPen(QColor("#fc8845"), 4))
        painter.drawArc(QRectF(-98, -95, 196, 190), 195 * 16, 115 * 16)
        painter.restore()

    def _floating_paper(self, painter: QPainter, progress: float) -> None:
        painter.save()
        x = 280 - 86 * progress
        y = 160 + 24 * progress - 15 * math.sin(math.pi * progress)
        painter.translate(x, y)
        painter.rotate(16 * (1 - progress))
        painter.setBrush(QColor("#f7e3b2"))
        painter.setPen(QPen(QColor("#d3914f"), 3))
        painter.drawRoundedRect(QRectF(-17, -23, 35, 45), 4, 4)
        painter.setPen(QPen(QColor("#9c6945"), 2))
        for yy in (-10, -2, 6, 14):
            painter.drawLine(-9, yy, 9, yy)
        painter.restore()

    def paintEvent(self, event) -> None:
        now = time.monotonic()
        state = self._phase
        progress = self.motion.progress(now=now)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.scale(self.width() / BASE_WIDTH, self.height() / BASE_HEIGHT)

        if state == "portal" and not self.reduced_motion:
            self._portal(painter, progress)

        if state != "sleep":
            # Tiny floor shadow follows the character and is not a background rectangle.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(8, 16, 22, 31))
            painter.drawEllipse(QRectF(85, 276, 182, 13))

        # State-dependent image transforms are cheap: this rasterized sprite
        # remains the same high-resolution, alpha-transparent original asset.
        dy = dx = tilt = 0.0
        sx = sy = 1.0
        if not self.reduced_motion:
            if state == "idle":
                dy = 1.9 * math.sin(now * 2.2)
                tilt = 1.15 * math.sin(now * .85)
                sy = 1.0 + .010 * math.sin(now * 2.2)
            elif state == "sleep":
                sy = .83 + .004 * math.sin(now * .8)
                sx = 1.065
                dy = 9
            elif state == "portal":
                sx = sy = .40 + .60 * min(1, progress * 1.25)
                dy = -12 * math.sin(progress * math.pi)
            elif state == "dash":
                dx = -68 * (1 - progress) ** 2
                sx = 1.07
                sy = .96
                dy = -17 * abs(math.sin(progress * math.pi * 3))
                tilt = -7 * math.sin(progress * math.pi)
            elif state == "catch":
                dy = -18 * math.sin(progress * math.pi)
                tilt = 9 * math.sin(progress * math.pi)
            elif state == "celebrate":
                dy = -18 * abs(math.sin(progress * math.pi * 2))
                tilt = 5 * math.sin(progress * math.pi * 4)
            elif state == "play":
                dy = -13 * abs(math.sin(progress * math.pi * 2))
                tilt = 8 * math.sin(progress * math.pi * 3)
            elif state == "wake":
                sy = .85 + .15 * progress
                dy = 9 * (1 - progress)
            elif state == "alert":
                tilt = 5 * math.sin(progress * math.pi)
            elif state == "guard":
                sy = 1.01
        else:
            if state == "sleep":
                sy = .9
                dy = 5

        painter.save()
        # Maintain a stationary ground anchor (280 px) while sleeping/squashing.
        painter.translate(170 + dx, 280 + dy)
        painter.rotate(tilt)
        painter.scale(sx, sy)
        painter.translate(-170, -280)
        painter.drawPixmap(QRectF(0, 33, 340, 257), self._sprite,
                           QRectF(0, 0, 720, 600))
        painter.restore()

        if state == "catch" and not self.reduced_motion:
            self._floating_paper(painter, progress)
        elif state == "celebrate" and not self.reduced_motion:
            painter.setPen(QPen(QColor("#ffc56c"), 3))
            for i in range(5):
                a = now * 2 + i * math.tau / 5
                x = 170 + 112 * math.cos(a)
                y = 135 + 73 * math.sin(a)
                painter.drawLine(int(x), int(y), int(x + 6 * math.cos(a)),
                                 int(y + 6 * math.sin(a)))

        if state == "sleep":
            painter.setPen(QColor("#ffd9aa"))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(20)
            painter.setFont(font)
            painter.drawText(QRectF(220, 47, 85, 55), Qt.AlignmentFlag.AlignCenter, "Zzz")
        elif now < self._message_until:
            painter.setBrush(QColor(17, 24, 34, 225))
            painter.setPen(QPen(QColor("#e59b55"), 1.5))
            painter.drawRoundedRect(QRectF(52, 1, 245, 34), 13, 13)
            painter.setPen(QColor("#ffe4bc"))
            font = painter.font()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            # The bubble will also respect user text size/layout at small scale.
            label = painter.fontMetrics().elidedText(
                self._message, Qt.TextElideMode.ElideRight, 230
            )
            painter.drawText(QRectF(60, 4, 228, 28),
                             Qt.AlignmentFlag.AlignCenter, label)
        painter.end()
