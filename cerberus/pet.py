"""Purely procedural desktop mascot and native drag-and-drop target."""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QApplication, QWidget


class CerberusPet(QWidget):
    capture_requested = Signal(str, object)
    vault_requested = Signal()
    menu_requested = Signal(QPoint)

    def __init__(self, *, reduced_motion: bool = False) -> None:
        super().__init__()
        self.setWindowTitle("Cerberus")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)
        self.setFixedSize(260, 230)
        self.reduced_motion = reduced_motion
        self._phase = "idle"
        self._started = time.monotonic()
        self._drag_offset: QPoint | None = None
        self._message = "Feed me a thought!"
        self._message_until = time.monotonic() + 4
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        if self._phase != "idle" and time.monotonic() - self._started > 1.25:
            self._phase = "idle"
            self._timer.setInterval(250)
        self.update()

    def tell(self, message: str, *, seconds: float = 2.8) -> None:
        self._message = message[:72]
        self._message_until = time.monotonic() + seconds
        self.update()

    def summon(self, message: str = "Caught!") -> None:
        cursor = QCursor.pos()
        screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            x = max(area.left(), min(cursor.x() - 125, area.right() - self.width() + 1))
            y = max(area.top(), min(cursor.y() - 110, area.bottom() - self.height() + 1))
            self.move(x, y)
        self.tell(message)
        self._phase = "idle" if self.reduced_motion else "portal"
        self._started = time.monotonic()
        self._timer.setInterval(250 if self.reduced_motion else 30)
        self.show()
        self.raise_()

    def dragEnterEvent(self, event) -> None:
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        mime = event.mimeData()
        if mime.hasUrls():
            files = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
            links = [u.toString() for u in mime.urls() if not u.isLocalFile()]
            if files:
                self.capture_requested.emit("files", files)
            for link in links:
                self.capture_requested.emit("text", link)
            event.acceptProposedAction()
        elif mime.hasText():
            self.capture_requested.emit("text", mime.text())
            event.acceptProposedAction()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.vault_requested.emit()

    def contextMenuEvent(self, event) -> None:
        self.menu_requested.emit(event.globalPos())

    @staticmethod
    def _polygon(*points: tuple[float, float]) -> QPolygonF:
        return QPolygonF([QPointF(x, y) for x, y in points])

    def _head(self, painter: QPainter, x: int, y: int, scale: float,
              expression: int, blinking: bool) -> None:
        painter.save()
        painter.translate(x, y)
        painter.scale(scale, scale)
        painter.setPen(QPen(QColor("#111b21"), 2))
        painter.setBrush(QColor("#242c36"))
        painter.drawPolygon(self._polygon((-25, -15), (-18, -43), (-3, -22)))
        painter.drawPolygon(self._polygon((6, -22), (20, -43), (26, -13)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#d66a42"))
        painter.drawPolygon(self._polygon((-18, -20), (-16, -34), (-8, -21)))
        painter.drawPolygon(self._polygon((12, -21), (19, -34), (20, -16)))
        painter.setPen(QPen(QColor("#131a21"), 2))
        painter.setBrush(QColor("#333c47"))
        painter.drawEllipse(QRectF(-27, -28, 54, 54))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#414951"))
        painter.drawEllipse(QRectF(-22, -9, 44, 31))
        painter.setBrush(QColor("#11161c"))
        painter.drawEllipse(QRectF(-6, 0, 12, 8))
        if not blinking:
            painter.setBrush(QColor("#ffad54"))
            painter.drawEllipse(QRectF(-15, -13, 8, 6))
            painter.drawEllipse(QRectF(8, -13, 8, 6))
            painter.setBrush(QColor("#fff1bc"))
            painter.drawEllipse(QRectF(-11, -12, 2, 2))
            painter.drawEllipse(QRectF(12, -12, 2, 2))
        else:
            painter.setPen(QPen(QColor("#fda04f"), 2))
            painter.drawLine(-16, -9, -8, -9)
            painter.drawLine(8, -9, 16, -9)
        painter.setPen(QPen(QColor("#161b20"), 2))
        if expression == 0:
            painter.drawArc(QRectF(-9, 2, 18, 13), 195 * 16, 150 * 16)
            painter.setBrush(QColor("#e87b7b"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(-2, 12, 7, 11))
        elif expression == 1:
            painter.drawArc(QRectF(-10, 4, 20, 10), 190 * 16, 160 * 16)
        else:
            painter.drawLine(-9, 12, 9, 11)
        painter.restore()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        t = time.monotonic() - self._started
        active = self._phase == "portal" and not self.reduced_motion
        if active:
            glow = max(0.0, 1.0 - t / 0.9)
            painter.save()
            painter.setOpacity(glow)
            painter.setPen(QPen(QColor("#20c7b2"), 7))
            painter.setBrush(QColor(10, 65, 65, 75))
            painter.drawEllipse(QRectF(22 + 25*t, 49, 215 - 50*t, 158))
            painter.setPen(QPen(QColor("#f49b50"), 3))
            painter.drawEllipse(QRectF(30 + 25*t, 55, 198 - 50*t, 147))
            painter.restore()
        now = time.monotonic()
        if now < self._message_until:
            painter.setPen(QPen(QColor("#dba46f"), 1))
            painter.setBrush(QColor(14, 24, 33, 240))
            painter.drawRoundedRect(QRectF(18, 4, 224, 34), 13, 13)
            painter.setPen(QColor("#f7e8ca"))
            painter.drawText(QRectF(24, 6, 212, 30),
                             Qt.AlignmentFlag.AlignCenter, self._message)
        bob = 0 if self.reduced_motion else 3 * math.sin(now * 2.1)
        jump = 0.0
        scale = 1.0
        if active:
            jump = -27 * math.sin(min(1, t / 0.7) * math.pi)
            scale = 0.58 + 0.42 * min(1, t / 0.45)
        painter.save()
        painter.translate(130, 130 + bob + jump)
        painter.scale(scale, scale)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(7, 17, 22, 90))
        painter.drawEllipse(QRectF(-74, 57 - jump / 3, 148, 20))
        # Tail, body, paws, collar, then the three independently posed heads.
        painter.setPen(QPen(QColor("#27333b"), 13, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(35, -4, 73, 64), 10 * 16, 200 * 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#222c36"))
        painter.drawEllipse(QRectF(-63, -30, 126, 92))
        painter.setBrush(QColor("#39424a"))
        painter.drawEllipse(QRectF(-53, 28, 37, 43))
        painter.drawEllipse(QRectF(19, 28, 37, 43))
        painter.setPen(QPen(QColor("#d79f53"), 5))
        painter.drawArc(QRectF(-47, -18, 94, 50), 195 * 16, 145 * 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#dba358"))
        painter.drawEllipse(QRectF(-8, 11, 16, 16))
        painter.setBrush(QColor("#1aa99f"))
        painter.drawEllipse(QRectF(-4, 15, 8, 8))
        blink = int(now * 1.7) % 13 == 0
        self._head(painter, -49, -24, 0.84, 0, blink)
        self._head(painter, 49, -24, 0.84, 2, blink)
        self._head(painter, 0, -46, 1.12, 1, blink)
        painter.restore()
        painter.end()
