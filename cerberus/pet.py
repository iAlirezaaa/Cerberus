"""Transparent animated Cerberus mascot for the user's actual desktop.

The character's GIF clips (or optional PNG frame sequences) are decoded once at
start-up. A small state machine picks which preloaded frame to paint; no asset
is decoded during painting. On top of the clips the widget adds life: it strolls
along the screen, turns toward the cursor, talks and thinks in bubbles, shows
particles, cross-fades between clips and draws an icon of what it caught.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import os
import random
import struct
import sys
import time
from importlib import resources
from pathlib import Path

from PySide6.QtCore import (
    QByteArray, QIODevice, QBuffer, QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal,
)
from PySide6.QtGui import (
    QColor, QCursor, QFont, QImage, QImageReader, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QPolygonF, QTransform,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QToolTip, QWidget

from .motion import MotionMachine
from .quips import QuipBook
from .animation_pack import (
    EXTRA_IDLE, MAX_DIMENSION, MAX_FRAME_BYTES, MAX_FRAMES_PER_STATE, MAX_UNIQUE_FRAMES,
    parse_manifest,
)

BASE_WIDTH = 340
BASE_HEIGHT = 380
# Budget for decoded source frames (before cropping, ~4 bytes each).
MAX_PACK_PIXELS = 96_000_000
MAX_RENDER_DIMENSION = 768
# GIF clips stand on this line (base coordinates) and are drawn at a fixed
# source-pixel scale so every clip keeps the same character size.
GROUND_Y = 372
SOURCE_SCALE = 0.80
# Speeds in base pixels per second.
LEAVE_SPEED = 430
WALK_SPEED = 95
ZOOMIES_SPEED = 390
FADE_SECONDS = 0.18
# Relative weights of the idle clips Cerberus rotates through.
IDLE_WEIGHTS = {"idle": 4, "idle_look": 2, "idle_wag": 2, "idle_wait": 2, "bark": 1}
# Seconds between spontaneous lines, per chat level.
CHAT_INTERVALS = {"off": None, "quiet": (150.0, 320.0), "normal": (55.0, 140.0),
                  "chatty": (22.0, 60.0)}
ROAM_INTERVAL = (16.0, 50.0)
# Hover button that sends Cerberus away (base coordinates).
DISMISS_RECT = QRectF(296, 86, 32, 32)
# Hover button that minimizes Cerberus into a small bubble.
MINIMIZE_RECT = QRectF(258, 86, 32, 32)
# Phases in which a one-off clip (petted, sad, talk, yawn…) may play over the base clip.
OVERRIDE_PHASES = ("idle", "play", "alert", "walk", "wake")


def parse_drop(mime) -> list[tuple[str, object]]:
    """Turn dropped data into capture requests: ("files", [...]), ("text", str), ("image", png)."""
    requests: list[tuple[str, object]] = []
    if mime.hasUrls():
        files = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
        links = [u.toString() for u in mime.urls() if not u.isLocalFile()]
        if files:
            requests.append(("files", files))
        requests.extend(("text", link) for link in links)
    elif mime.hasText():
        requests.append(("text", mime.text()))
    elif mime.hasImage():
        png = mime_image_png(mime)
        if png is not None:
            requests.append(("image", png))
    return requests


def accepts_drop(mime) -> bool:
    return bool(mime.hasUrls() or mime.hasText() or mime.hasImage())


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
    """Use the replacement Cerberus as the fallback for invalid optional packs."""
    raw = resources.files("cerberus").joinpath("assets/characters/cerberus/00.png").read_bytes()
    pixmap = QPixmap()
    if not pixmap.loadFromData(raw, "PNG"):
        raise RuntimeError("Bundled Cerberus fallback is invalid")
    return pixmap


def _load_png(data: bytes, name: str) -> QPixmap:
    if not data or len(data) > MAX_FRAME_BYTES:
        raise ValueError(f"Animation frame is empty or too large: {name}")
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"Animation asset is not a valid PNG: {name}")
    width, height = struct.unpack(">II", data[16:24])
    if not width or not height or width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise ValueError(f"Animation frame dimensions exceed {MAX_DIMENSION}px: {name}")
    pixmap = QPixmap()
    if not pixmap.loadFromData(data, "PNG") or pixmap.isNull():
        raise ValueError(f"Could not decode animation PNG: {name}")
    if pixmap.width() > MAX_DIMENSION or pixmap.height() > MAX_DIMENSION:
        raise ValueError(f"Animation frame dimensions exceed {MAX_DIMENSION}px: {name}")
    if not pixmap.toImage().hasAlphaChannel():
        raise ValueError(f"Animation frame must support transparency: {name}")
    if pixmap.width() > MAX_RENDER_DIMENSION or pixmap.height() > MAX_RENDER_DIMENSION:
        pixmap = pixmap.scaled(
            MAX_RENDER_DIMENSION, MAX_RENDER_DIMENSION,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return pixmap


def _alpha_bounds(image: QImage, threshold: int = 8) -> tuple[int, int, int, int] | None:
    """Tight (left, top, right, bottom) box of visible pixels in an ARGB32 image."""
    width, height, stride = image.width(), image.height(), image.bytesPerLine()
    raw = bytes(image.constBits())
    offset = 3 if sys.byteorder == "little" else 0
    rows = [raw[r * stride + offset: r * stride + 4 * width: 4] for r in range(height)]
    visible = [r for r, row in enumerate(rows) if max(row) > threshold]
    if not visible:
        return None
    plane = b"".join(rows[visible[0]: visible[-1] + 1])
    columns = [c for c in range(width) if max(plane[c::width]) > threshold]
    return columns[0], visible[0], columns[-1] + 1, visible[-1] + 1


@dataclass(frozen=True)
class _Gif:
    frames: tuple[QPixmap, ...]
    delays: tuple[float, ...]
    offset: tuple[int, int]
    pixels: int


def _load_gif(data: bytes, name: str) -> _Gif:
    """Decode every GIF frame once and crop all frames to their shared visible box."""
    if not data or len(data) > MAX_FRAME_BYTES:
        raise ValueError(f"Animation GIF is empty or too large: {name}")
    if len(data) < 10 or data[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError(f"Animation asset is not a valid GIF: {name}")
    width, height = struct.unpack("<HH", data[6:10])
    if not width or not height or width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise ValueError(f"Animation GIF dimensions exceed {MAX_DIMENSION}px: {name}")
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    if not buffer.open(QIODevice.OpenModeFlag.ReadOnly):
        raise ValueError(f"Could not read animation GIF: {name}")
    reader = QImageReader(buffer, QByteArray(b"gif"))
    images: list[QImage] = []
    delays: list[float] = []
    while True:
        image = reader.read()
        if image.isNull():
            break
        if len(images) >= MAX_FRAMES_PER_STATE:
            raise ValueError(f"Animation GIF has more than {MAX_FRAMES_PER_STATE} frames: {name}")
        if image.width() > MAX_DIMENSION or image.height() > MAX_DIMENSION:
            raise ValueError(f"Animation GIF dimensions exceed {MAX_DIMENSION}px: {name}")
        images.append(image.convertToFormat(QImage.Format.Format_ARGB32))
        delay = reader.nextImageDelay()
        delays.append(max(0.02, (delay if delay > 0 else 100) / 1000))
    buffer.close()
    if not images:
        raise ValueError(f"Could not decode animation GIF: {name}")
    if not images[0].hasAlphaChannel() or images[0].pixelColor(0, 0).alpha() != 0:
        raise ValueError(f"Animation GIF must have a transparent background: {name}")
    frames, offset, pixels = _crop_shared(images, name)
    return _Gif(frames, tuple(delays), offset, pixels)


def _crop_shared(images: list[QImage], name: str) -> tuple[tuple[QPixmap, ...], tuple[int, int], int]:
    """Crop every frame to the union of their visible boxes (keeps frames aligned)."""
    boxes = [box for box in (_alpha_bounds(image) for image in images) if box]
    if not boxes:
        raise ValueError(f"Animation clip is fully transparent: {name}")
    pad = 2
    left = max(0, min(b[0] for b in boxes) - pad)
    top = max(0, min(b[1] for b in boxes) - pad)
    right = min(images[0].width(), max(b[2] for b in boxes) + pad)
    bottom = min(images[0].height(), max(b[3] for b in boxes) + pad)
    frames = tuple(
        QPixmap.fromImage(image.copy(left, top, right - left, bottom - top))
        for image in images
    )
    return frames, (left, top), (right - left) * (bottom - top) * len(images)


@dataclass(frozen=True)
class _Clip:
    """Preloaded frames for one state; ``anchored`` clips stand on the ground line."""

    frames: tuple[QPixmap, ...]
    delays: tuple[float, ...]
    loop: bool = False
    loop_from: int = 0
    scale: float = 1.0
    anchored: bool = False
    # Per-frame box of the carried item, in the cropped frame's pixels.
    props: tuple[QRectF | None, ...] = ()

    @property
    def total(self) -> float:
        return sum(self.delays)

    @property
    def rest(self) -> QPixmap:
        """Single frame shown when motion is reduced."""
        return self.frames[self.loop_from if self.loop else 0]

    def index_at(self, elapsed: float) -> int:
        if len(self.frames) == 1:
            return 0
        elapsed = max(0.0, elapsed)
        total = self.total
        if elapsed >= total:
            if not self.loop:
                return len(self.frames) - 1
            loop_start = sum(self.delays[: self.loop_from])
            elapsed = loop_start + (elapsed - loop_start) % (total - loop_start)
        position = 0.0
        for index, delay in enumerate(self.delays):
            position += delay
            if elapsed < position:
                return index
        return len(self.frames) - 1


def _load_animation_pack(character: str = "cerberus") -> tuple[_Clip, dict[str, _Clip], str]:
    """Eagerly load a local pack; invalid optional packs fall back to the original SVG."""
    override = os.environ.get("CERBERUS_ASSET_PACK")
    if character not in ("cerberus", "ghost", "hades", "charon"):
        character = "cerberus"
    try:
        if override:
            manifest_path = Path(override).expanduser().resolve()
            if manifest_path.stat().st_size > 256 * 1024:
                raise ValueError("Animation manifest is too large")
            root = manifest_path.parent
            manifest = parse_manifest(manifest_path.read_bytes())

            def read_asset(name: str) -> bytes:
                candidate = root / Path(*name.split("/"))
                path = candidate.resolve()
                if candidate.is_symlink() or not path.is_relative_to(root) or not path.is_file():
                    raise ValueError(f"Animation asset is outside its pack: {name}")
                if path.stat().st_size > MAX_FRAME_BYTES:
                    raise ValueError(f"Animation frame is too large: {name}")
                return path.read_bytes()
        else:
            root = resources.files("cerberus").joinpath("assets", "characters", character)
            manifest = parse_manifest(root.joinpath("animation-pack.json").read_bytes())

            def read_asset(name: str) -> bytes:
                return root.joinpath(*name.split("/")).read_bytes()

        names = {manifest.default}
        for sequence in manifest.states.values():
            names.update(sequence.frames)
            if sequence.gif:
                names.add(sequence.gif)
        if len(names) > MAX_UNIQUE_FRAMES:
            raise ValueError("Animation pack contains too many unique frames")
        png_cache: dict[str, QPixmap] = {}
        gif_cache: dict[str, _Gif] = {}
        total_pixels = 0

        def charge(pixels: int) -> None:
            nonlocal total_pixels
            total_pixels += pixels
            if total_pixels > MAX_PACK_PIXELS:
                raise ValueError("Animation pack exceeds the decoded pixel budget")

        def load_png(name: str) -> QPixmap:
            if name not in png_cache:
                data = read_asset(name)
                if (len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n"
                        or data[12:16] != b"IHDR"):
                    raise ValueError(f"Animation asset is not a valid PNG: {name}")
                width, height = struct.unpack(">II", data[16:24])
                charge(width * height)
                png_cache[name] = _load_png(data, name)
            return png_cache[name]

        def load_gif(name: str) -> _Gif:
            if name not in gif_cache:
                gif = _load_gif(read_asset(name), name)
                charge(gif.pixels)
                gif_cache[name] = gif
            return gif_cache[name]

        clips: dict[str, _Clip] = {}
        for state, sequence in manifest.states.items():
            if sequence.gif:
                gif = load_gif(sequence.gif)
                frames, delays = gif.frames, gif.delays
                if sequence.fps_explicit:
                    delays = (1 / sequence.fps,) * len(frames)
                if sequence.props and len(sequence.props) != len(frames):
                    raise ValueError(f"{state} props must list one box per frame")
                left, top = gif.offset
                props = tuple(
                    None if box is None else QRectF(box[0] - left, box[1] - top,
                                                    box[2] - box[0], box[3] - box[1])
                    for box in sequence.props
                )
                anchored = True
            else:
                frames = tuple(load_png(name) for name in sequence.frames)
                if len({(frame.width(), frame.height()) for frame in frames}) != 1:
                    raise ValueError(f"All frames in {state} must use the same canvas")
                delays = (1 / sequence.fps,) * len(frames)
                props = ()
                anchored = sequence.anchored
                if anchored:
                    # Soft-alpha PNG clips are cropped and grounded exactly like GIFs.
                    images = [frame.toImage().convertToFormat(QImage.Format.Format_ARGB32)
                              for frame in frames]
                    frames, (left, top), _ = _crop_shared(images, state)
                    props = tuple(
                        None if box is None else QRectF(box[0] - left, box[1] - top,
                                                        box[2] - box[0], box[3] - box[1])
                        for box in sequence.props
                    )
            if sequence.loop_from >= len(frames):
                raise ValueError(f"{state} loop_from is past the last frame")
            if sequence.reverse:
                frames, delays, props = frames[::-1], delays[::-1], props[::-1]
            clips[state] = _Clip(frames, delays, sequence.loop, sequence.loop_from,
                                 sequence.scale, anchored, props)
        idle = clips.get("idle")
        if idle is not None and idle.anchored and manifest.default.lower().endswith(".png") \
                and manifest.default in (states_first := {
                    state: seq.frames[0] for state, seq in manifest.states.items() if seq.frames
                }).values():
            # Default pose = the idle clip's own cropped first frame (tray icon, bubble face).
            default = _Clip(idle.frames[:1], idle.delays[:1], scale=idle.scale, anchored=True)
        elif manifest.default.lower().endswith(".gif"):
            gif = load_gif(manifest.default)
            scale = next((clip.scale for clip in clips.values()
                          if clip.frames[0] is gif.frames[0]), 1.0)
            default = _Clip(gif.frames[:1], gif.delays[:1], scale=scale, anchored=True)
        else:
            default = _Clip((load_png(manifest.default),), (1.0,))
        return default, clips, "raster-pack"
    except (OSError, ValueError, TypeError, RuntimeError):
        return _Clip((_sprite_pixmap(),), (1.0,)), {}, "svg-fallback"


@dataclass(frozen=True)
class CarryIcon:
    """What Cerberus is carrying: drawn over the scroll / document in its paws."""

    kind: str  # "text", "url", "image" or "file"
    pixmap: QPixmap | None = None
    label: str = ""


@dataclass
class _Particle:
    kind: str
    x: float
    y: float
    vx: float
    vy: float
    born: float
    life: float
    size: float = 1.0


def _bubble_font(point_size: float = 10.5) -> QFont:
    font = QFont()
    font.setFamilies(["Segoe UI", "Tahoma", "Arial"])
    font.setPointSizeF(point_size)
    font.setBold(True)
    return font


class CerberusPet(QWidget):
    capture_requested = Signal(str, object)
    vault_requested = Signal()
    menu_requested = Signal(QPoint)
    dismiss_requested = Signal()
    minimize_requested = Signal()
    went_away = Signal(int, int)  # side (-1 left, 1 right), last y position
    came_back = Signal()

    def __init__(self, *, reduced_motion: bool = False,
                 standby_seconds: float = 95.0,
                 away_seconds: float | None = None,
                 roam: bool = False, chat_level: str = "off",
                 language: str = "en", character: str = "cerberus") -> None:
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
        self.setToolTip("Cerberus — drop text, links, images or files here; "
                        "double-click to search; hover for the send-away button.")
        self.reduced_motion = reduced_motion
        self.motion = MotionMachine(
            standby_after=standby_seconds, reduced_motion=reduced_motion,
            away_after=away_seconds,
        )
        self.roam = roam
        self.chat_level = chat_level if chat_level in CHAT_INTERVALS else "off"
        self.quips = QuipBook(language, character=character)
        self._default_clip, self._state_frames, self._sprite_source = _load_animation_pack(character)
        self._sprite = self._default_clip.frames[0]
        # Transient phases last exactly one pass of the clip that was loaded for them.
        for phase in list(self.motion.durations):
            clip = self._state_frames.get(phase)
            if clip is not None and clip.anchored and not clip.loop:
                self.motion.set_duration(phase, clip.total)
        stash = self._state_frames.get("stash_item")
        if stash is not None:
            self.motion.set_duration("celebrate", stash.total)
        self._override: str | None = None
        self._override_started = 0.0
        self._override_until = 0.0
        self._override_mirror: bool | None = None
        self._frozen = False
        self._mirrored: dict[int, QPixmap] = {}
        self._size = BASE_WIDTH
        self.setFixedSize(BASE_WIDTH, BASE_HEIGHT)
        self._drag_offset: QPoint | None = None
        self._press_position: QPoint | None = None
        self._dragged = False
        self._hovered = False
        self._message = ""
        self._message_style = "say"
        self._message_until = 0.0
        self._variant: str | None = None
        self._variant_started = 0.0
        self._variant_until = 0.0
        self._play_visual = "play"
        self._facing = 1
        self._leave_dir = 0
        self._walk_target = 0.0
        self._walk_x = 0.0
        self._walk_speed = WALK_SPEED
        self._walk_visual = "walk"
        self._carry: CarryIcon | None = None
        self._particles: list[_Particle] = []
        self._next_dust = 0.0
        self._next_z = 0.0
        self._last_paint_key: tuple | None = None
        self._last_paint: tuple[QPixmap, QRectF] | None = None
        self._fade_from: tuple[QPixmap, QRectF] | None = None
        self._fade_started = 0.0
        self._prev_phase = self.motion.phase
        start = time.monotonic()
        self._last_tick = start
        self._next_chat_at = start + self._chat_delay()
        self._next_roam_at = start + random.uniform(8.0, 20.0)
        self._next_face_check = start
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(180)
        self._timer.start()
        self.place_at_screen_corner()

    # ----- state helpers -------------------------------------------------
    @property
    def _phase(self) -> str:
        """Legacy public-ish state used by the original GUI smoke test."""
        return self.motion.phase

    @property
    def is_away(self) -> bool:
        return self.motion.is_away

    def _chat_delay(self) -> float:
        window = CHAT_INTERVALS.get(self.chat_level)
        return random.uniform(*window) if window else 1e9

    def place_at_screen_corner(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is not None:
            g = screen.availableGeometry()
            self.move(
                max(g.left(), g.right() - self.width() - 22),
                max(g.top(), g.bottom() - self.height() + 4),
            )

    def _area(self) -> QRect | None:
        screen = self.screen() or QApplication.primaryScreen()
        return screen.availableGeometry() if screen is not None else None

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

    # ----- public controls ----------------------------------------------
    def set_pet_size(self, width: int) -> None:
        """Small/medium/large sizes preserve aspect ratio and visible position."""
        width = max(180, min(500, int(width)))
        origin = self.pos()
        self._size = width
        self.setFixedSize(width, round(BASE_HEIGHT * width / BASE_WIDTH))
        if not self.is_away:
            self.move(self._on_screen(origin.x(), origin.y()))
        self.update()

    def set_reduced_motion(self, enabled: bool) -> None:
        self.reduced_motion = enabled
        self.motion.reduced_motion = enabled
        self.update()

    def set_away_after(self, seconds: float | None) -> None:
        """Seconds of no interaction before Cerberus runs off-screen (None = never)."""
        self.motion.away_after = seconds
        self.motion.last_active_at = time.monotonic()

    def set_roam(self, enabled: bool) -> None:
        self.roam = enabled
        if not enabled and self._phase == "walk":
            self.motion.settle()

    def set_chat_level(self, level: str) -> None:
        self.chat_level = level if level in CHAT_INTERVALS else "normal"
        self._next_chat_at = time.monotonic() + self._chat_delay()

    def set_language(self, language: str) -> None:
        self.quips = QuipBook(language, character=self.quips.character)

    def tell(self, message: str, *, seconds: float = 2.8, style: str = "say") -> None:
        self._message = message[:90]
        self._message_style = style
        self._message_until = time.monotonic() + seconds
        self.update()

    def say(self, event: str, *, force: bool = False, chance: float = 1.0,
            style: str = "say", **values: object) -> None:
        """Speak a line for an event (skipped when chat is off, unless forced)."""
        if (self.chat_level == "off" and not force) or random.random() > chance:
            return
        line = self.quips.pick(event, **values)
        if line:
            seconds = min(6.0, 2.2 + len(line) / 18)
            self.tell(line, seconds=seconds, style=style)
            # Mouth moves while talking / paw-on-chin while thinking, when those clips exist
            # (only while sitting idle, so a stroll or a capture is never interrupted).
            if self._phase == "idle":
                self.play_clip("think" if style == "think" else "talk", seconds=seconds)

    def play_clip(self, name: str, *, seconds: float | None = None, loops: int = 1,
                  mirror: bool | None = None) -> bool:
        """Play an optional one-off clip over the current phase (if the pack has it)."""
        clip = self._state_frames.get(name)
        if clip is None or self.reduced_motion or self._phase not in OVERRIDE_PHASES:
            return False
        now = time.monotonic()
        self._override = name
        self._override_started = now
        self._override_until = now + (seconds if seconds is not None else clip.total * loops)
        self._override_mirror = mirror
        return True

    def _active_override(self, now: float) -> str | None:
        if self._override is None:
            return None
        if now >= self._override_until or self._phase not in OVERRIDE_PHASES:
            self._override = None
            self._override_mirror = None
            return None
        return self._override

    def sad(self) -> None:
        """Capture failed: droop (when the clip exists) and say so."""
        self.play_clip("sad")
        self.say("error", force=True)

    def greet(self) -> None:
        if self.chat_level != "off":
            line = self.quips.greeting()
            self.tell(line, seconds=4.0)

    def _wake_up(self) -> None:
        """Restart animation after being away (the timer is stopped while hidden)."""
        was_hidden = not self.isVisible()
        self._leave_dir = 0
        self._last_tick = time.monotonic()
        if not self._timer.isActive():
            self._timer.start()
        self.show()
        self.raise_()
        if was_hidden:
            self.came_back.emit()

    def _move_to_cursor(self) -> None:
        cursor = QCursor.pos()
        self.move(self._on_screen(cursor.x() - self.width() // 2,
                                  cursor.y() - self.height() * 2 // 3))

    def summon(self, message: str = "Caught!", carry: CarryIcon | None = None) -> None:
        """Summon from the portal at the current mouse position after capture."""
        self._move_to_cursor()
        self._carry = carry
        self.motion.capture()
        self.tell(message, seconds=4.5)
        self._wake_up()
        self._tick()

    def arrive(self, message: str = "", *, at: QPoint | None = None) -> None:
        """Come back through the Hades portal at the cursor (or with feet at ``at``)."""
        self._frozen = False
        if at is None:
            self._move_to_cursor()
        else:
            feet = GROUND_Y * self.height() / BASE_HEIGHT
            self.move(self._on_screen(at.x() - self.width() // 2, round(at.y() - feet)))
        # An active transition: restoring must not make it run off straight away.
        self.motion.arrive()
        if message:
            self.tell(message, seconds=2.4)
        self._spawn_burst("spark", 14, 170, GROUND_Y - 30, spread=120)
        self._wake_up()
        self._tick()

    def feet_position(self) -> QPoint:
        """Global point between Cerberus's feet (where a minimized bubble should sit)."""
        return self.mapToGlobal(QPoint(self.width() // 2,
                                       round(GROUND_Y * self.height() / BASE_HEIGHT)))

    def freeze(self) -> None:
        """Minimized: hide and stop every timer so it costs no CPU."""
        self._frozen = True
        self._timer.stop()
        self._particles.clear()
        self._override = None
        if self.is_away:
            self.motion.transition("idle")
        self.hide()

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    def vanish(self, then) -> None:
        """Hop into a portal (when that clip exists), then call ``then``."""
        clip = self._state_frames.get("portal_exit")
        if clip is None or self.reduced_motion or not self.isVisible():
            then()
            return
        self.motion.transition("idle")
        self.play_clip("portal_exit")
        self._tick()
        QTimer.singleShot(int(clip.total * 1000), then)

    def dismiss(self) -> None:
        """Send Cerberus away on purpose: it says goodbye and runs off-screen."""
        if self.is_away or self._frozen:
            return
        self.say("dismiss", force=True)
        self.motion.dismiss()
        self._wake_up()
        self._tick()

    def play(self, action: str = "play") -> None:
        if action not in ("play", "alert", "wake", "sleep", "guard", "idle"):
            raise ValueError("Invalid pet action")
        if self.is_away:
            self.place_at_screen_corner()
        self.motion.transition(action)
        if action == "sleep":
            self.tell("Zzz…", seconds=2)
        elif action == "guard":
            self.tell("Guard mode", seconds=2)
        elif action == "play":
            self._play_visual = "play"
            self.say("pet", force=True)
        self._wake_up()
        self._tick()

    # ----- behaviour -----------------------------------------------------
    def _pick_idle_variant(self, now: float) -> None:
        weights = dict(IDLE_WEIGHTS)
        for extra in EXTRA_IDLE:
            weights[extra] = 1
        hour = time.localtime().tm_hour
        if hour >= 20 or hour < 5:
            weights["howl"] = 1  # only at night
        options = [(name, weight) for name, weight in weights.items()
                   if name == "idle" or name in self._state_frames]
        if self.reduced_motion or self._variant is None:
            choice = "idle"
        else:
            # Avoid playing the same flourish twice in a row.
            pool = [(n, w) for n, w in options if n != self._variant or n == "idle"]
            choice = random.choices([n for n, _ in pool], [w for _, w in pool])[0]
        self._set_variant(choice, now)

    def _set_variant(self, choice: str, now: float, loops: int | None = None) -> None:
        clip = self._state_frames.get(choice)
        length = clip.total if clip is not None else 2.0
        if loops is None:
            if choice == "idle":
                loops = random.randint(2, 4)
            elif choice in ("bark", "howl", *EXTRA_IDLE) and choice != "chase_tail":
                loops = 1
            else:
                loops = 2
        self._variant = choice
        self._variant_started = now
        self._variant_until = now + max(1.5, length * loops)

    def _start_walk(self, now: float, *, zoomies: bool = False) -> bool:
        area = self._area()
        if area is None or self._drag_offset is not None:
            return False
        low, high = area.left(), area.right() - self.width() + 1
        if high - low < 220:
            return False
        target = self.x()
        for _ in range(8):
            target = random.randint(low, high)
            if abs(target - self.x()) >= 160:
                break
        if abs(target - self.x()) < 120:
            return False
        self._walk_target = float(target)
        self._walk_x = float(self.x())
        self._walk_speed = ZOOMIES_SPEED if zoomies else WALK_SPEED
        self._walk_visual = "leave" if zoomies else "walk"
        self._facing = 1 if target > self.x() else -1
        self.motion.transition("walk", now=now)
        # Get up before moving off (when the bridge clip exists).
        self._walk_hold_until = now
        if self.play_clip("sit_to_run"):
            self._walk_hold_until = self._override_until
        if not zoomies:
            self.say("walk", chance=0.25)
        return True

    def _walk_step(self, now: float, dt: float) -> None:
        if self._drag_offset is not None or now < getattr(self, "_walk_hold_until", 0.0):
            return
        step = self._facing * self._walk_speed * dt * self.width() / BASE_WIDTH
        self._walk_x += step
        done = (self._facing > 0 and self._walk_x >= self._walk_target) or \
               (self._facing < 0 and self._walk_x <= self._walk_target)
        if done:
            self._walk_x = self._walk_target
        self.move(round(self._walk_x), self.y())
        if done:
            self.motion.settle(now=now)
            self.play_clip("run_to_sit")
            self._next_roam_at = now + random.uniform(*ROAM_INTERVAL)

    def _leave_step(self, now: float, dt: float) -> None:
        """Run toward the nearest edge of the current screen, then hide."""
        screen = self.screen() or QApplication.primaryScreen()
        if self.reduced_motion or screen is None:
            self._finish_leave()
            return
        area = screen.geometry()
        if self._leave_dir == 0:
            centre = self.x() + self.width() / 2
            self._leave_dir = 1 if centre >= area.center().x() else -1
            self._walk_x = float(self.x())
        self._facing = self._leave_dir
        self._walk_x += self._leave_dir * LEAVE_SPEED * dt * self.width() / BASE_WIDTH
        self.move(round(self._walk_x), self.y())
        if (self._leave_dir > 0 and self.x() > area.right()) or \
                (self._leave_dir < 0 and self.x() + self.width() < area.left()):
            self._finish_leave()

    def _finish_leave(self) -> None:
        side = self._leave_dir or 1
        self.motion.transition("away")
        self._leave_dir = 0
        self._particles.clear()
        self._timer.stop()
        self.hide()
        self.went_away.emit(side, self.y() + self.height())

    def _face_cursor(self, now: float) -> None:
        if now < self._next_face_check:
            return
        self._next_face_check = now + 1.1
        cursor = QCursor.pos()
        centre = self.geometry().center()
        dx = cursor.x() - centre.x()
        if abs(dx) > self.width() * 0.55 and abs(cursor.y() - centre.y()) < 1200:
            facing = 1 if dx > 0 else -1
            if facing != self._facing and self._override is None:
                # The turn clip goes right -> left; mirrored it goes left -> right.
                self.play_clip("turn_around", mirror=facing > 0)
            self._facing = facing

    def _on_phase_change(self, old: str, new: str, now: float) -> None:
        if new == "sleep":
            self.say("sleep", chance=0.6)
        elif new == "wake" and old == "sleep":
            self.say("wake", chance=0.6)
        elif new == "rouse" or (new == "leave" and old in ("idle", "sleep")):
            self.say("leave", chance=0.9)
        elif new == "celebrate":
            self._spawn_burst("spark", 10, 230, GROUND_Y - 150, spread=70)
        elif new == "idle":
            self._carry = None
            self._variant = None

    def _spawn_burst(self, kind: str, count: int, x: float, y: float, *,
                     spread: float = 60) -> None:
        if self.reduced_motion:
            return
        now = time.monotonic()
        for i in range(count):
            angle = (i / max(1, count)) * math.tau + random.uniform(-.3, .3)
            speed = random.uniform(.4, 1.0) * spread
            self._particles.append(_Particle(
                kind, x, y, math.cos(angle) * speed, math.sin(angle) * speed - 30,
                now, random.uniform(.7, 1.2), random.uniform(.7, 1.3)))

    def _spawn_hearts(self) -> None:
        if self.reduced_motion:
            return
        now = time.monotonic()
        for i in range(5):
            self._particles.append(_Particle(
                "heart", 170 + random.uniform(-70, 70), 150 + random.uniform(-20, 30),
                random.uniform(-14, 14), random.uniform(-70, -40),
                now + i * 0.08, random.uniform(1.1, 1.6), random.uniform(.8, 1.3)))

    def _ambient_particles(self, phase: str, now: float) -> None:
        if self.reduced_motion:
            return
        if phase in ("walk", "leave", "dash") and now >= self._next_dust:
            self._next_dust = now + (0.12 if phase != "walk" else 0.22)
            back = 170 - self._facing * 85
            self._particles.append(_Particle(
                "dust", back + random.uniform(-12, 12), GROUND_Y - 6,
                -self._facing * random.uniform(15, 35), random.uniform(-18, -6),
                now, random.uniform(.5, .8), random.uniform(.8, 1.4)))
        elif phase == "sleep" and now >= self._next_z:
            self._next_z = now + 1.3
            self._particles.append(_Particle(
                "z", 170 + self._facing * 70, GROUND_Y - 150, self._facing * 10, -24,
                now, 2.6, random.uniform(.8, 1.2)))
        if len(self._particles) > 60:
            del self._particles[:-60]

    def _tick(self) -> None:
        if self._frozen:
            self._timer.stop()
            return
        now = time.monotonic()
        dt = min(0.1, max(0.0, now - self._last_tick))
        self.motion.update(now=now)
        phase = self._phase
        if phase != self._prev_phase:
            self._on_phase_change(self._prev_phase, phase, now)
            self._prev_phase = phase
        if phase == "away":
            self._timer.stop()
            self.hide()
            return
        if phase == "leave":
            self._leave_step(now, dt)
            if self._phase == "away":
                return
        else:
            self._leave_dir = 0
        if phase == "walk":
            self._walk_step(now, dt)
        if phase == "idle":
            if self._variant is None or now >= self._variant_until:
                self._pick_idle_variant(now)
            if self._drag_offset is None and not self.reduced_motion:
                if self.roam:
                    self._face_cursor(now)
                    if now >= self._next_roam_at:
                        if not self._start_walk(now, zoomies=random.random() < 0.15):
                            self._next_roam_at = now + random.uniform(*ROAM_INTERVAL)
                if self.chat_level != "off" and now >= self._next_chat_at:
                    self._next_chat_at = now + self._chat_delay()
                    if random.random() < 0.45:
                        self._set_variant(random.choice(["idle_wait", "idle_look"]), now, loops=2)
                        self.say("think", style="think")
                    else:
                        self.say("idle")
        elif phase != "walk":
            self._variant = None
        self._ambient_particles(phase, now)
        self._particles = [p for p in self._particles if now - p.born < p.life]
        self._last_tick = now
        if phase in ("sleep", "guard"):
            target_interval = 120 if not self.reduced_motion else 900
        elif phase == "idle":
            target_interval = 50 if not self.reduced_motion else 500
        else:
            target_interval = 33 if not self.reduced_motion else 200
        if self._timer.isActive() and self._timer.interval() != target_interval:
            self._timer.setInterval(target_interval)
        self.update()

    # ----- input ---------------------------------------------------------
    def _base_point(self, point: QPointF) -> QPointF:
        return QPointF(point.x() * BASE_WIDTH / self.width(),
                       point.y() * BASE_HEIGHT / self.height())

    def _dismiss_visible(self) -> bool:
        return self._hovered and self._phase not in ("leave", "away", "rouse")

    def dragEnterEvent(self, event) -> None:
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasText() or mime.hasImage():
            event.acceptProposedAction()
            self.motion.transition("alert")
            self.say("drag_over", force=True)
            self.play_clip("sniff", seconds=self.motion.durations["alert"][0])
            self._spawn_burst("bang", 1, 170 + self._facing * 40, 110, spread=1)
            self._wake_up()
            self._tick()

    def dragMoveEvent(self, event) -> None:
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasText() or mime.hasImage():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        requests = parse_drop(event.mimeData())
        for kind, value in requests:
            self.capture_requested.emit(kind, value)
        if requests:
            event.acceptProposedAction()

    def enterEvent(self, event) -> None:
        self._hovered = True
        if self._phase == "sleep":
            self.motion.transition("wake")
            self._tick()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            point = self._base_point(event.position())
            if self._dismiss_visible():
                for rect, signal in ((DISMISS_RECT, self.dismiss_requested),
                                     (MINIMIZE_RECT, self.minimize_requested)):
                    if rect.adjusted(-4, -4, 4, 4).contains(point):
                        self._press_position = None
                        self._drag_offset = None
                        signal.emit()
                        event.accept()
                        return
            if self._phase == "walk":
                self.motion.settle()
            self._press_position = event.globalPosition().toPoint()
            self._drag_offset = self._press_position - self.frameGeometry().topLeft()
            self._dragged = False
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            point = event.globalPosition().toPoint()
            if self._press_position is not None and (point - self._press_position).manhattanLength() >= 6:
                if not self._dragged:
                    self.say("dragged", chance=0.5)
                    self.play_clip("held", seconds=3600)  # until released
                self._dragged = True
            if self._dragged:
                desired = point - self._drag_offset
                self.move(self._on_screen(desired.x(), desired.y()))
            event.accept()
        elif self._hovered:
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._press_position is not None:
            if not self._dragged:
                self.motion.touch()
                if self._phase == "play":
                    choices = [name for name in ("play", "happy", "petted", "celebrate_jump")
                               if name in self._state_frames] or ["play"]
                    self._play_visual = random.choice(choices)
                    self._spawn_hearts()
                    self.say("pet", force=True)
                self._tick()
            else:
                # Being carried around counts as attention too.
                self.motion.last_active_at = time.monotonic()
                if self._override == "held":
                    self._override = None
        self._drag_offset = None
        self._press_position = None
        self._dragged = False

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.vault_requested.emit()
            event.accept()

    def contextMenuEvent(self, event) -> None:
        self.menu_requested.emit(event.globalPos())

    # ----- painting ------------------------------------------------------
    def _visual_state(self, state: str) -> str:
        """Machine phase, or the clip currently standing in for it."""
        override = self._active_override(time.monotonic())
        if override is not None:
            return override
        if state == "celebrate" and "stash_item" in self._state_frames:
            return "stash_item"
        if state == "idle" and self._variant in self._state_frames:
            return self._variant
        if state == "play" and self._play_visual in self._state_frames:
            return self._play_visual
        if state == "walk" and self._walk_visual in self._state_frames:
            return self._walk_visual
        return state

    def _clip_for(self, visual: str) -> _Clip:
        return self._state_frames.get(visual, self._default_clip)

    def _target_rect(self, clip: _Clip, sprite: QPixmap) -> QRectF:
        scale = SOURCE_SCALE * clip.scale
        width, height = sprite.width() * scale, sprite.height() * scale
        return QRectF(BASE_WIDTH / 2 - width / 2, GROUND_Y - height, width, height)

    def paintEvent(self, event) -> None:
        now = time.monotonic()
        state = self._phase
        visual = self._visual_state(state)
        clip = self._clip_for(visual)
        progress = self.motion.progress(now=now)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.scale(self.width() / BASE_WIDTH, self.height() / BASE_HEIGHT)

        if clip.anchored and visual in self._state_frames:
            # Authored GIF clips carry their own motion: no procedural transforms.
            if state not in ("portal", "arrive", "sleep") and visual != "portal_exit":
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(8, 16, 22, 31))
                painter.drawEllipse(QRectF(90, GROUND_Y - 9, 170, 12))
            index = self._frame_index(visual, now)
            sprite = clip.rest if self.reduced_motion else clip.frames[index]
            mirrored = self._facing < 0
            if visual == self._override and self._override_mirror is not None:
                mirrored = self._override_mirror
            if mirrored:
                sprite = self._mirror(sprite)
            target = self._target_rect(clip, sprite)
            key = (visual, mirrored)
            if key != self._last_paint_key and self._last_paint is not None \
                    and not self.reduced_motion:
                self._fade_from = self._last_paint
                self._fade_started = now
            self._last_paint_key = key
            # New pose solid underneath, old pose fading out on top: the body never turns
            # see-through, and switching clips blends instead of popping.
            painter.drawPixmap(target, sprite, QRectF(sprite.rect()))
            fade = (now - self._fade_started) / FADE_SECONDS if self._fade_from else 1.0
            if fade < 1.0 and self._fade_from is not None:
                old_sprite, old_rect = self._fade_from
                painter.setOpacity((1.0 - fade) ** 1.5)
                painter.drawPixmap(old_rect, old_sprite, QRectF(old_sprite.rect()))
                painter.setOpacity(1.0)
            else:
                self._fade_from = None
            self._last_paint = (sprite, target)
            if self._carry is not None and clip.props and not self.reduced_motion:
                box = clip.props[min(index, len(clip.props) - 1)]
                if box is not None:
                    self._draw_carry(painter, clip, sprite, target, box, mirrored)
        else:
            self._paint_legacy(painter, state, visual, progress, now)

        self._paint_particles(painter, now)
        if state == "sleep" and not self._state_frames:
            painter.setBrush(QColor(255, 190, 105, 130))
            painter.setPen(QPen(QColor("#ffc76d"), 1.4))
            painter.drawEllipse(QRectF(244, 160, 6, 6))
            painter.drawEllipse(QRectF(257, 140, 10, 10))
            painter.drawEllipse(QRectF(276, 113, 15, 15))
        if now < self._message_until and self._message:
            self._draw_bubble(painter, self._message, self._message_style)
        if self._dismiss_visible():
            self._draw_dismiss(painter)
        painter.end()

    def _draw_carry(self, painter: QPainter, clip: _Clip, sprite: QPixmap,
                    target: QRectF, box: QRectF, mirrored: bool) -> None:
        """Paint an icon of the captured item over the scroll/document in the clip."""
        scale = target.width() / sprite.width()
        x = sprite.width() - box.right() if mirrored else box.left()
        rect = QRectF(target.left() + x * scale, target.top() + box.top() * scale,
                      box.width() * scale, box.height() * scale)
        card = rect.adjusted(rect.width() * .1, rect.height() * .1,
                             -rect.width() * .1, -rect.height() * .16)
        carry = self._carry
        painter.save()
        gradient = QLinearGradient(card.topLeft(), card.bottomRight())
        gradient.setColorAt(0, QColor("#ffe29a"))
        gradient.setColorAt(1, QColor("#ff8f2e"))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(255, 244, 214, 220), 1.2))
        painter.drawRoundedRect(card, 3, 3)
        inner = card.adjusted(3, 3, -3, -3)
        ink = QColor("#6b2410")
        if carry.pixmap is not None and not carry.pixmap.isNull():
            pix = carry.pixmap
            room = inner.adjusted(0, 0, 0, -7 if carry.label else 0)
            ratio = min(room.width() / pix.width(), room.height() / pix.height())
            w, h = pix.width() * ratio, pix.height() * ratio
            painter.drawPixmap(QRectF(room.center().x() - w / 2, room.center().y() - h / 2, w, h),
                               pix, QRectF(pix.rect()))
        elif carry.kind == "url":
            painter.setPen(QPen(ink, 1.6))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r = min(inner.width(), inner.height()) * .42
            c = inner.center()
            painter.drawEllipse(c, r, r)
            painter.drawEllipse(c, r * .45, r)
            painter.drawLine(QPointF(c.x() - r, c.y()), QPointF(c.x() + r, c.y()))
        else:
            painter.setPen(QPen(ink, 1.6))
            for i in range(4):
                y = inner.top() + inner.height() * (0.18 + i * 0.2)
                end = inner.right() - (inner.width() * .3 if i == 3 else 0)
                painter.drawLine(QPointF(inner.left() + 1, y), QPointF(end, y))
        if carry.label:
            font = _bubble_font(5.5)
            painter.setFont(font)
            painter.setPen(ink)
            painter.drawText(QRectF(card.left(), card.bottom() - 9, card.width(), 9),
                             Qt.AlignmentFlag.AlignCenter, carry.label[:5])
        painter.restore()

    def _paint_particles(self, painter: QPainter, now: float) -> None:
        if not self._particles:
            return
        painter.save()
        for p in self._particles:
            age = now - p.born
            if age < 0 or age >= p.life:
                continue
            t = age / p.life
            x = p.x + p.vx * age
            y = p.y + p.vy * age + (40 * age * age if p.kind == "spark" else 0)
            painter.setOpacity(max(0.0, 1.0 - t) * (0.6 if p.kind == "dust" else 1.0))
            if p.kind == "heart":
                s = 9 * p.size
                path = QPainterPath()
                path.moveTo(x, y + s * .35)
                path.cubicTo(x - s, y - s * .4, x - s * .35, y - s, x, y - s * .45)
                path.cubicTo(x + s * .35, y - s, x + s, y - s * .4, x, y + s * .35)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#ff5d7a"))
                painter.drawPath(path)
            elif p.kind == "dust":
                r = (5 + 9 * t) * p.size
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(120, 96, 84, 120))
                painter.drawEllipse(QPointF(x, y), r, r * .7)
            elif p.kind == "spark":
                painter.setPen(QPen(QColor("#ffc56c"), 2.2))
                r = 4 * p.size
                painter.drawLine(QPointF(x - r, y), QPointF(x + r, y))
                painter.drawLine(QPointF(x, y - r), QPointF(x, y + r))
            elif p.kind in ("z", "bang"):
                painter.setFont(_bubble_font((11 + 8 * t) * p.size if p.kind == "z" else 20))
                painter.setPen(QColor("#ffc76d") if p.kind == "z" else QColor("#ff7a3c"))
                painter.drawText(QPointF(x, y), "z" if p.kind == "z" else "!")
        painter.restore()

    def _draw_bubble(self, painter: QPainter, text: str, style: str) -> None:
        painter.save()
        font = _bubble_font(10.5)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        flags = int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap)
        bounds = metrics.boundingRect(QRect(0, 0, 270, 400), flags, text)
        width = min(270, bounds.width()) + 26
        height = min(bounds.height(), metrics.lineSpacing() * 2 + 2) + 16
        x = max(4.0, min(BASE_WIDTH - width - 4.0, BASE_WIDTH / 2 - width / 2 + 14))
        box = QRectF(x, 4, width, height)
        tail_x = max(box.left() + 18, min(box.right() - 18, 170 + self._facing * 30))
        if style == "think":
            painter.setPen(QPen(QColor("#e9b98c"), 1.5))
            painter.setBrush(QColor(252, 246, 238, 238))
            painter.drawRoundedRect(box, height / 2, height / 2)
            painter.drawEllipse(QPointF(tail_x, box.bottom() + 8), 5, 5)
            painter.drawEllipse(QPointF(tail_x + self._facing * 7, box.bottom() + 19), 3, 3)
            painter.setPen(QColor("#4a2a22"))
        else:
            painter.setPen(QPen(QColor("#e59b55"), 1.5))
            painter.setBrush(QColor(17, 24, 34, 232))
            path = QPainterPath()
            path.addRoundedRect(box, 13, 13)
            tail = QPolygonF([QPointF(tail_x - 9, box.bottom() - 1),
                              QPointF(tail_x + 9, box.bottom() - 1),
                              QPointF(tail_x + self._facing * 4, box.bottom() + 13)])
            tail_path = QPainterPath()
            tail_path.addPolygon(tail)
            painter.drawPath(path.united(tail_path))
            painter.setPen(QColor("#ffe4bc"))
        painter.drawText(box.adjusted(12, 7, -12, -7), flags, text)
        painter.restore()

    def _draw_dismiss(self, painter: QPainter) -> None:
        """Small portal button: click to send Cerberus away."""
        painter.save()
        rect = DISMISS_RECT
        painter.setPen(QPen(QColor("#ee703c"), 2))
        painter.setBrush(QColor(28, 18, 20, 225))
        painter.drawEllipse(rect)
        painter.setPen(QPen(QColor("#ffd29a"), 2.2, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        c = rect.center()
        painter.drawLine(QPointF(c.x() - 6, c.y() + 6), QPointF(c.x() + 6, c.y() - 6))
        painter.drawLine(QPointF(c.x() + 6, c.y() - 6), QPointF(c.x() - 1, c.y() - 6))
        painter.drawLine(QPointF(c.x() + 6, c.y() - 6), QPointF(c.x() + 6, c.y() + 1))
        # Minimize button: a short bar.
        rect = MINIMIZE_RECT
        painter.setPen(QPen(QColor("#ee703c"), 2))
        painter.setBrush(QColor(28, 18, 20, 225))
        painter.drawEllipse(rect)
        painter.setPen(QPen(QColor("#ffd29a"), 2.6, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        m = rect.center()
        painter.drawLine(QPointF(m.x() - 7, m.y() + 3), QPointF(m.x() + 7, m.y() + 3))
        painter.restore()

    def _paint_legacy(self, painter: QPainter, state: str, visual: str,
                      progress: float, now: float) -> None:
        """Single-pose PNG / SVG character animated with whole-body transforms."""
        if state in ("portal", "arrive") and not self.reduced_motion:
            self._portal(painter, progress)
        if state != "sleep":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(8, 16, 22, 31))
            painter.drawEllipse(QRectF(85, GROUND_Y - 12, 182, 13))
        has_frames = visual in self._state_frames
        dy = dx = tilt = 0.0
        sx = sy = 1.0
        if not self.reduced_motion:
            if state == "idle":
                dy = 1.9 * math.sin(now * 2.2)
                tilt = 1.15 * math.sin(now * .85)
                sy = 1.0 + .010 * math.sin(now * 2.2)
            elif state == "sleep":
                sy = 1.0 + .006 * math.sin(now * .8) if has_frames else .83
                sx = 1.0 if has_frames else 1.065
                dy = 9
            elif state in ("portal", "arrive"):
                sx = sy = .40 + .60 * min(1, progress * 1.25)
                dy = -12 * math.sin(progress * math.pi)
            elif state in ("dash", "leave", "walk"):
                sx, sy = 1.07, .96
                dy = -17 * abs(math.sin(now * math.pi * (3 if state != "walk" else 1.5)))
            elif state == "catch":
                dy = -18 * math.sin(progress * math.pi)
                tilt = 9 * math.sin(progress * math.pi)
            elif state == "celebrate":
                dy = -18 * abs(math.sin(progress * math.pi * 2))
                tilt = 5 * math.sin(progress * math.pi * 4)
            elif state == "play":
                dy = -13 * abs(math.sin(progress * math.pi * 2))
                tilt = 8 * math.sin(progress * math.pi * 3)
            elif state == "carry":
                dy = -4 * abs(math.sin(progress * math.pi * 2))
            elif state in ("wake", "rouse"):
                sy = .85 + .15 * progress
                dy = 9 * (1 - progress)
            elif state == "alert":
                tilt = 5 * math.sin(progress * math.pi)
        elif state == "sleep":
            sy = 1.0 if has_frames else .9
            dy = 5
        ground = GROUND_Y - 10
        painter.save()
        painter.translate(170 + dx, ground + dy)
        painter.rotate(tilt)
        painter.scale(-sx if self._facing < 0 else sx, sy)
        painter.translate(-170, -ground)
        sprite = self._frame_for_state(visual, now)
        source = QRectF(sprite.rect())
        bounds = QRectF(0, ground - 257, BASE_WIDTH, 257)
        scale = min(bounds.width() / source.width(), bounds.height() / source.height())
        width, height = source.width() * scale, source.height() * scale
        target = QRectF((BASE_WIDTH - width) / 2,
                        bounds.top() + (bounds.height() - height) / 2, width, height)
        if self._default_clip.anchored:
            target = self._target_rect(self._default_clip, sprite)
        painter.drawPixmap(target, sprite, source)
        if self._carry is not None and state in ("catch", "carry", "celebrate"):
            # A floating offering follows every identity without assuming a dog's mouth.
            self._draw_carry(painter, self._default_clip, sprite, target,
                             QRectF(sprite.width() * .63, sprite.height() * .52,
                                    sprite.width() * .2, sprite.width() * .2), False)
        painter.restore()

    def _portal(self, painter: QPainter, progress: float) -> None:
        painter.save()
        painter.setOpacity(max(0.05, 1.0 - progress * .75))
        painter.translate(155, GROUND_Y - 150)
        painter.rotate(190 * progress)
        painter.setBrush(QColor("#30221e"))
        painter.setPen(QPen(QColor("#ee703c"), 7))
        painter.drawEllipse(QRectF(-92, -90, 184, 180))
        painter.setPen(QPen(QColor("#ffbf6b"), 2))
        painter.drawEllipse(QRectF(-82, -80, 164, 160))
        painter.restore()

    def _mirror(self, sprite: QPixmap) -> QPixmap:
        """Left-facing copy of a frame, cached so painting never re-transforms."""
        key = sprite.cacheKey()
        if key not in self._mirrored:
            self._mirrored[key] = sprite.transformed(QTransform().scale(-1, 1))
        return self._mirrored[key]

    def _frame_index(self, state: str, now: float) -> int:
        clip = self._state_frames.get(state)
        if clip is None:
            return 0
        if state == self._override:
            started = self._override_started
        elif state == self._variant:
            started = self._variant_started
        else:
            started = self.motion.entered_at
        return clip.index_at(now - started)

    def _frame_for_state(self, state: str, now: float) -> QPixmap:
        """Select a preloaded frame from the clip's own timeline."""
        clip = self._state_frames.get(state)
        if clip is None:
            return self._sprite
        if self.reduced_motion:
            return clip.rest
        return clip.frames[self._frame_index(state, now)]


class MiniBubble(QWidget):
    """Small round Cerberus bubble: the minimized mode, and the dock while it is away.

    Click to bring Cerberus back, drag to move, drop things on it to save them without
    restoring, right-click for the menu. It is a still image unless hovered or
    flashing, so it costs no CPU while it waits.
    """

    clicked = Signal()
    dropped = Signal(str, object)
    moved = Signal(QPoint)
    menu_requested = Signal(QPoint)

    def __init__(self, face: QPixmap | None = None, curl: _Clip | None = None,
                 size: int = 72, reduced_motion: bool = False) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAcceptDrops(True)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Cerberus — click to bring back, drop things here to save them, "
                        "drag to move, right-click for the menu")
        self.reduced_motion = reduced_motion
        self._curl = curl
        self._face = None
        if face is not None and not face.isNull():
            # Use the top part of the sprite: the three heads.
            head = face.copy(0, 0, face.width(), int(face.height() * .55))
            inner = int(size * .7)
            self._face = head.scaled(inner, inner, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
        self._phase = 0.0
        self._started = time.monotonic()
        self._hover = False
        self._drop_hover = False
        self._flash_until = 0.0
        self._press: QPoint | None = None
        self._origin = QPoint()
        self._moved = False
        self._timer = QTimer(self)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._spin)

    # ----- placement -------------------------------------------------------
    def show_at(self, side: int, bottom_y: int, screen=None) -> None:
        """Dock at the left/right screen edge (used while Cerberus is away)."""
        screen = screen or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = area.right() - self.width() - 6 if side > 0 else area.left() + 6
        y = max(area.top(), min(bottom_y - self.height() - 10, area.bottom() - self.height() - 6))
        self.move(x, y)
        self._show()

    def show_centered(self, point: QPoint) -> None:
        """Sit with its bottom-centre at ``point`` (e.g. where Cerberus's feet were)."""
        target = QPoint(point.x() - self.width() // 2, point.y() - self.height())
        self.move(self._clamp(target))
        self._show()

    def _clamp(self, top_left: QPoint) -> QPoint:
        centre = top_left + QPoint(self.width() // 2, self.height() // 2)
        screen = QApplication.screenAt(centre) or QApplication.primaryScreen()
        if screen is None:
            return top_left
        area = screen.availableGeometry()
        return QPoint(max(area.left(), min(top_left.x(), area.right() - self.width() + 1)),
                      max(area.top(), min(top_left.y(), area.bottom() - self.height() + 1)))

    def _show(self) -> None:
        self.show()
        self.raise_()
        self._update_timer()

    def hide(self) -> None:  # noqa: D401 - Qt override
        self._timer.stop()
        super().hide()

    def flash(self, message: str = "") -> None:
        """Brief celebration after something was saved while minimized."""
        self._flash_until = time.monotonic() + 1.6
        self._update_timer()
        if message and self.isVisible():
            QToolTip.showText(self.mapToGlobal(QPoint(self.width() // 2, 0)), message, self)

    # ----- animation -------------------------------------------------------
    def _animating(self) -> bool:
        return not self.reduced_motion and (
            self._hover or self._drop_hover or time.monotonic() < self._flash_until)

    def _update_timer(self) -> None:
        if self._animating() and self.isVisible():
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _spin(self) -> None:
        self._phase = (self._phase + 0.18) % math.tau
        if not self._animating():
            self._timer.stop()
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        size = self.width()
        rect = QRectF(4, 4, size - 8, size - 8)
        active = self._animating()
        glow = 0.75 + 0.25 * math.sin(self._phase * 2) if active else 0.85
        ring = QColor(255, 200, 90) if self._drop_hover else QColor(238, 112, 60)
        ring.setAlpha(int(255 * glow))
        p.setPen(QPen(ring, 4))
        p.setBrush(QColor(36, 20, 20, 230))
        p.drawEllipse(rect)
        p.setPen(QPen(QColor("#ffbf6b"), 1.6))
        p.drawArc(rect.adjusted(5, 5, -5, -5), int(math.degrees(self._phase) * 16), 200 * 16)
        if self._curl is not None:
            clip = self._curl
            index = clip.index_at(time.monotonic() - self._started) if active else 0
            frame = clip.frames[index]
            box = rect.adjusted(6, 6, -6, -6)
            ratio = min(box.width() / frame.width(), box.height() / frame.height())
            w, h = frame.width() * ratio, frame.height() * ratio
            p.drawPixmap(QRectF(box.center().x() - w / 2, box.center().y() - h / 2, w, h),
                         frame, QRectF(frame.rect()))
        elif self._face is not None:
            bob = 2 * math.sin(self._phase * 2) if active else 0
            p.drawPixmap(int(size / 2 - self._face.width() / 2),
                         int(size / 2 + 2 - self._face.height() / 2 + bob), self._face)
        p.end()

    # ----- input -----------------------------------------------------------
    def enterEvent(self, event) -> None:
        self._hover = True
        self._update_timer()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self._update_timer()
        super().leaveEvent(event)

    def dragEnterEvent(self, event) -> None:
        if accepts_drop(event.mimeData()):
            event.acceptProposedAction()
            self._drop_hover = True
            self._update_timer()

    def dragMoveEvent(self, event) -> None:
        if accepts_drop(event.mimeData()):
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self._drop_hover = False
        self._update_timer()

    def dropEvent(self, event) -> None:
        self._drop_hover = False
        requests = parse_drop(event.mimeData())
        for kind, value in requests:
            self.dropped.emit(kind, value)
        if requests:
            event.acceptProposedAction()
        self._update_timer()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._origin = self.pos()
            self._moved = False

    def mouseMoveEvent(self, event) -> None:
        if self._press is not None:
            delta = event.globalPosition().toPoint() - self._press
            if delta.manhattanLength() > 5:
                self._moved = True
            if self._moved:
                self.move(self._clamp(self._origin + delta))

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._press is not None:
            if self._moved:
                self.moved.emit(self.pos())
            else:
                self.clicked.emit()
        self._press = None

    def contextMenuEvent(self, event) -> None:
        self.menu_requested.emit(event.globalPos())


# Older name kept for callers and tests.
ReturnButton = MiniBubble
