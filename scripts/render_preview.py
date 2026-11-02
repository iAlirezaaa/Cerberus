"""Render real Cerberus window states on an offscreen Qt platform for QA.

Run: python scripts/render_preview.py
Requires the gui extra plus Pillow. Outputs PNG and an animated GIF in preview/.
"""
from __future__ import annotations

import io
import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtWidgets import QApplication

from cerberus.motion import DURATIONS
from cerberus.pet import CerberusPet

OUT = Path("preview")
OUT.mkdir(exist_ok=True)
app = QApplication.instance() or QApplication([])
pet = CerberusPet()
pet.show()
app.processEvents()


def snapshot(phase: str, fraction: float = 0.0) -> Image.Image:
    pet.motion.transition(phase)
    duration = DURATIONS.get(phase, (0.0, ""))[0]
    pet.motion.entered_at = time.monotonic() - fraction * duration
    pet.update()
    app.processEvents()
    pix = pet.grab()
    if pix.isNull():
        raise RuntimeError(f"Could not render state: {phase}")
    buffer = io.BytesIO()
    # save to a Qt byte array and convert via Pillow instead of screen capture.
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    qt_data = QByteArray()
    qt_buffer = QBuffer(qt_data)
    qt_buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not pix.save(qt_buffer, "PNG"):
        raise RuntimeError("Qt PNG export failed")
    image = Image.open(io.BytesIO(bytes(qt_data))).convert("RGBA")
    return image


states = ["idle", "portal", "dash", "catch", "celebrate", "sleep"]
tiles = []
for phase in states:
    frame = snapshot(phase, 0.45 if phase in DURATIONS else 0)
    frame.save(OUT / f"cerberus-{phase}.png")
    tiles.append(frame)

width, height = tiles[0].size
sheet = Image.new("RGBA", (width * 3, height * 2), (0, 0, 0, 0))
for i, tile in enumerate(tiles):
    sheet.alpha_composite(tile, ((i % 3) * width, (i // 3) * height))
sheet.save(OUT / "cerberus-state-sheet.png")

# A short loop of authentic GUI frames: wake -> portal -> dash -> catch -> celebrate -> rest.
frames = []
for phase, count in [("wake", 5), ("portal", 6), ("dash", 8),
                     ("catch", 7), ("celebrate", 8), ("idle", 10), ("sleep", 10)]:
    for i in range(count):
        progress = i / max(1, count - 1)
        frames.append(snapshot(phase, progress))
# GIF is a compatibility preview only: PNG frames retain true 8-bit alpha.
frames[0].save(
    OUT / "cerberus-animation-preview.gif",
    save_all=True, append_images=frames[1:],
    duration=80, loop=0, disposal=2, optimize=False,
)
pet.close()
print(f"Rendered {len(tiles)} PNG states and {len(frames)} animated frames to {OUT.resolve()}")
