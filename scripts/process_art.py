"""Turn generated sheets / frame folders into clean, consistent Cerberus clips.

Usage:
  python scripts/process_art.py sheet  <sheet.png> <out_dir> <clip_name>
  python scripts/process_art.py frames <frames_dir> <out_dir> <clip_name>
  python scripts/process_art.py gifs                   # smooth the bundled GIFs into PNG clips

Steps (code only cuts, aligns, rescales and cleans pixels the artist/generator made):
1. Background removal: real alpha is kept; a flat or checkerboard light background touching the
   border is flood-filled away, then a 1 px fringe is trimmed.
2. Pose extraction by connected components (never a fixed grid), small detached bits (sparks,
   props) are attached to the nearest pose.
3. Normalisation: every clip is rescaled so its reference pose is as wide as the approved idle
   pose, and placed on a 320 x 640 canvas with the feet on y = 490. "Grounded" clips have each
   frame's feet pinned (no drift or jitter); "rigid" clips (lifted, jumping, sinking) keep their
   own vertical motion and only the first frame is pinned.
4. Edge smoothing: GIF-style one-bit edges get a soft 1 px alpha edge.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageSequence

REPO = Path(__file__).resolve().parents[1]
GIFS = REPO / "cerberus" / "assets" / "gifs"
CANVAS = (480, 640)  # wider than the GIFs so heads/tails never clip; the app crops anyway
BASELINE = 490
CENTRE_X = 240
# Clips that leave the ground or sink: keep their own vertical motion.
RIGID = {"held", "portal_exit", "celebrate_jump", "chase_tail", "peek_in", "sit_to_run"}
# Which frame shows the pose to measure for size (default: first).
REFERENCE_FRAME = {"wake_up": -1, "stash_item": -1, "run_to_sit": -1}
# Moving clips are sized against the run cycle, everything else against idle.
SIZE_FROM_RUN = {"walk", "sit_to_run", "run_to_sit"}


def alpha_box(image: Image.Image, threshold: int = 40):
    return image.getchannel("A").point(lambda a: 255 if a > threshold else 0).getbbox()


def approved_width(name: str) -> int:
    gif = "run" if name in SIZE_FROM_RUN else "idle_breathe"
    widths = []
    for frame in ImageSequence.Iterator(Image.open(GIFS / f"{gif}.gif")):
        box = alpha_box(frame.convert("RGBA"))
        widths.append(box[2] - box[0])
    return int(statistics.median(widths))


def soften_edges(image: Image.Image) -> Image.Image:
    """Give one-bit alpha a soft 1 px edge without growing the shape."""
    alpha = image.getchannel("A")
    soft = ImageChops.darker(alpha, alpha.filter(ImageFilter.BoxBlur(1)))
    out = image.copy()
    out.putalpha(soft)
    return out


def remove_background(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    alpha = image.getchannel("A")
    transparent = alpha.resize((64, 64)).histogram()[:10]
    transparent = sum(transparent)
    if transparent > 64 * 64 * 0.25:
        return image  # real transparency already
    w, h = image.size
    px = image.load()

    def background(x: int, y: int) -> bool:
        r, g, b, _ = px[x, y]
        return min(r, g, b) > 165 and max(r, g, b) - min(r, g, b) < 30

    mask = Image.new("L", (w, h), 255)
    mp = mask.load()
    queue = deque()
    for x in range(w):
        queue.extend(((x, 0), (x, h - 1)))
    for y in range(h):
        queue.extend(((0, y), (w - 1, y)))
    while queue:
        x, y = queue.popleft()
        if mp[x, y] == 0 or not background(x, y):
            continue
        mp[x, y] = 0
        if x > 0: queue.append((x - 1, y))
        if x < w - 1: queue.append((x + 1, y))
        if y > 0: queue.append((x, y - 1))
        if y < h - 1: queue.append((x, y + 1))
    # Background pockets enclosed by the body (between legs, under the tail) are not connected to
    # the border; remove any light grey region big enough to be background, not teeth/highlights.
    for y0 in range(h):
        for x0 in range(w):
            if mp[x0, y0] != 255 or not background(x0, y0):
                continue
            region, queue = [], deque([(x0, y0)])
            mp[x0, y0] = 128
            while queue:
                x, y = queue.popleft()
                region.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and mp[nx, ny] == 255 and background(nx, ny):
                        mp[nx, ny] = 128
                        queue.append((nx, ny))
            value = 0 if len(region) >= 120 else 255
            for x, y in region:
                mp[x, y] = value
    mask = mask.filter(ImageFilter.MinFilter(3))  # trim the light fringe
    image.putalpha(ImageChops.darker(alpha, mask))
    return image


def components(image: Image.Image, scale: int = 4):
    small = image.getchannel("A").resize((max(1, image.width // scale), max(1, image.height // scale)))
    w, h = small.size
    px = small.load()
    seen = bytearray(w * h)
    found = []
    for y in range(h):
        for x in range(w):
            if px[x, y] > 60 and not seen[y * w + x]:
                queue = deque([(x, y)])
                seen[y * w + x] = 1
                area, x0, y0, x1, y1 = 0, x, y, x, y
                while queue:
                    cx, cy = queue.popleft()
                    area += 1
                    x0, y0, x1, y1 = min(x0, cx), min(y0, cy), max(x1, cx), max(y1, cy)
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx] and px[nx, ny] > 60:
                            seen[ny * w + nx] = 1
                            queue.append((nx, ny))
                found.append([area, x0 * scale, y0 * scale, (x1 + 1) * scale, (y1 + 1) * scale])
    return found


def poses_from_sheet(sheet: Image.Image) -> list[tuple[Image.Image, int]]:
    """Each pose cropped from the sheet, with its top y in sheet coordinates."""
    parts = components(sheet)
    if not parts:
        return []
    biggest = max(p[0] for p in parts)
    bodies = [p for p in parts if p[0] >= biggest * 0.15]
    for bit in (p for p in parts if p[0] < biggest * 0.15):
        cx = (bit[1] + bit[3]) / 2
        owner = min(bodies, key=lambda b: abs((b[1] + b[3]) / 2 - cx))
        if abs((owner[1] + owner[3]) / 2 - cx) < (owner[3] - owner[1]):
            owner[1:] = [min(owner[1], bit[1]), min(owner[2], bit[2]),
                         max(owner[3], bit[3]), max(owner[4], bit[4])]
    bodies.sort(key=lambda b: b[1])
    poses = []
    for _, x0, y0, x1, y1 in bodies:
        pad = 4
        box = (max(0, x0 - pad), max(0, y0 - pad), min(sheet.width, x1 + pad), min(sheet.height, y1 + pad))
        crop = sheet.crop(box)
        tight = alpha_box(crop, 10)
        if tight:
            poses.append((crop.crop(tight), box[1] + tight[1]))
    return poses


def poses_from_frames(folder: Path) -> list[tuple[Image.Image, int]]:
    poses = []
    for path in sorted(folder.glob("*.png")):
        frame = Image.open(path).convert("RGBA")
        box = alpha_box(frame, 10)
        if box:
            poses.append((frame.crop(box), box[1]))
    return poses


def feet(pose: Image.Image) -> tuple[float, int]:
    """Centre x of the lowest quarter of the body, and the bottom y."""
    h = pose.height
    lower = pose.crop((0, int(h * 0.75), pose.width, h))
    box = alpha_box(lower, 60) or (0, 0, pose.width, 1)
    return (box[0] + box[2]) / 2, h


def normalise(name: str, poses: list[tuple[Image.Image, int]], canvas=CANVAS,
              baseline=BASELINE, centre_x=CENTRE_X, target_width: int | None = None) -> list[Image.Image]:
    ref = poses[REFERENCE_FRAME.get(name, 0)][0]
    target = target_width or approved_width(name)
    scale = target / ref.width
    scaled = [(p.resize((max(1, round(p.width * scale)), max(1, round(p.height * scale))),
                        Image.LANCZOS), top * scale) for p, top in poses]
    ref_top = scaled[REFERENCE_FRAME.get(name, 0)][1]
    ref_h = scaled[REFERENCE_FRAME.get(name, 0)][0].height
    frames = []
    for pose, top in scaled:
        fx, bottom = feet(pose)
        if name in RIGID:
            y = round(baseline - ref_h + (top - ref_top))  # keep its own up/down motion
        else:
            y = baseline - bottom                          # pin the feet
        x = round(centre_x - fx)
        frame = Image.new("RGBA", canvas, (0, 0, 0, 0))
        frame.alpha_composite(pose, (max(-pose.width, x), max(-pose.height, y)))
        frames.append(soften_edges(frame))
    return frames


def save(frames: list[Image.Image], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    for index, frame in enumerate(frames, 1):
        frame.save(out / f"{index:02d}.png", optimize=True)


PACK = REPO / "cerberus" / "assets" / "animation-pack.json"


def smooth_gifs() -> dict:
    """Convert the bundled GIF clips to soft-edged PNG frames and point the pack at them.

    Same canvas, timing, loops, props and scale; only the jagged one-bit edges change.
    """
    timing = {}
    for gif in sorted(GIFS.glob("*.gif")):
        image = Image.open(gif)
        frames, delays = [], []
        for frame in ImageSequence.Iterator(image):
            frames.append(soften_edges(frame.convert("RGBA")))
            delays.append(frame.info.get("duration", 100) or 100)
        save(frames, REPO / "cerberus" / "assets" / "clips" / f"gif_{gif.stem}")
        timing[gif.stem] = {"frames": len(frames), "fps": round(1000 / statistics.mean(delays), 3)}
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    for state, entry in pack["states"].items():
        gif = entry.get("gif")
        if not gif:
            continue
        stem = Path(gif).stem
        entry.pop("gif")
        entry["frames"] = [f"clips/gif_{stem}/{i:02d}.png" for i in range(1, timing[stem]["frames"] + 1)]
        entry.setdefault("fps", timing[stem]["fps"])
        entry["anchored"] = True
    if pack.get("default", "").endswith(".gif"):
        pack["default"] = f"clips/gif_{Path(pack['default']).stem}/01.png"
    PACK.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return timing


def main(argv: list[str]) -> int:
    if argv[:1] == ["gifs"]:
        print(json.dumps(smooth_gifs(), indent=1))
        return 0
    mode, source, out, name = argv[0], Path(argv[1]), Path(argv[2]), argv[3]
    if mode == "sheet":
        poses = poses_from_sheet(remove_background(Image.open(source)))
    else:
        poses = poses_from_frames(source)
    if len(poses) < 4:
        print(f"{name}: only {len(poses)} poses found")
        return 1
    if name.startswith("mini_"):
        frames = normalise(name, poses, canvas=(96, 96), baseline=90, centre_x=48, target_width=86)
    else:
        frames = normalise(name, poses)
    save(frames, out)
    print(f"{name}: {len(frames)} frames -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
