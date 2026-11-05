"""The art QA gate must reject fake animations (repeated, moved or flickering frames)."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:  # Pillow is only needed for art tooling
    Image = None

ROOT = Path(__file__).resolve().parents[1]


def load_qa():
    spec = importlib.util.spec_from_file_location("qa_codex_art", ROOT / "scripts" / "qa_codex_art.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dog(pose: int, dx: int = 0, scale: float = 1.0):
    """A crude 'character' on the 320x640 canvas whose pose changes with ``pose``."""
    image = Image.new("RGBA", (320, 640), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    w = int(200 * scale)
    left = 60 + dx
    # The body squashes and stretches and a big tail sweeps around as the pose changes.
    height = int((200 + pose * 14) * scale)
    d.ellipse((left, 490 - height, left + w, 490), fill=(90, 40, 30, 255))
    tx = left + pose * 24
    d.ellipse((tx, 260 - pose * 10, tx + 110, 370 - pose * 10), fill=(255, 140, 40, 255))
    return image


@unittest.skipIf(Image is None, "Pillow not installed")
class ArtQaTests(unittest.TestCase):
    def setUp(self):
        self.qa = load_qa()

    def frames(self, images):
        folder = Path(tempfile.mkdtemp())
        for index, image in enumerate(images, 1):
            image.save(folder / f"{index:02d}.png")
        return folder

    def test_real_motion_passes(self):
        result = self.qa.check("tail_wag", self.frames([dog(i % 6) for i in range(8)]))
        self.assertTrue(result["pass"], result["problems"])

    def test_repeated_frame_fails(self):
        result = self.qa.check("walk", self.frames([dog(2)] * 8))
        self.assertFalse(result["pass"])
        self.assertTrue(any("identical" in p or "barely moves" in p for p in result["problems"]))

    def test_moved_or_scaled_copy_fails(self):
        images = [dog(2, dx=(i % 4) * 6, scale=1.0 - (i % 3) * 0.02) for i in range(8)]
        result = self.qa.check("celebrate_jump", self.frames(images))
        self.assertFalse(result["pass"])
        self.assertTrue(any("pose" in p for p in result["problems"]), result["problems"])

    def test_two_frame_flicker_fails(self):
        result = self.qa.check("chase_tail", self.frames([dog(i % 2 * 5) for i in range(8)]))
        self.assertFalse(result["pass"])

    def test_identical_icons_fail(self):
        folder = Path(tempfile.mkdtemp())
        for kind in ("pdf", "video", "audio"):
            icon = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
            ImageDraw.Draw(icon).rectangle((30, 20, 98, 108), fill=(255, 140, 40, 255))
            icon.save(folder / f"{kind}.png")
        report = self.qa.check_icons(folder)
        self.assertFalse(any(r["pass"] for r in report.values()))


if __name__ == "__main__":
    unittest.main()
