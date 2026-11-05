"""Automatic quality gate for generated Cerberus animation frames.

Usage: python scripts/qa_codex_art.py [art/codex]   (requires Pillow)

For every art/codex/frames/<name>/NN.png sequence it checks: one shared canvas,
transparent corners, exactly one character body per frame (catches sheets sliced
across two cells), no slivers cut off at the cell edges, stable scale between
frames and feet on the baseline. Writes art/codex/qa_report.json and prints a summary.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

BASELINE = 490
# Clips that legitimately leave the ground, enter from an edge, or include props.
AIRBORNE = {"held", "portal_exit", "chase_tail", "celebrate_jump", "sit_to_run", "stash_item"}
EDGE_OK = {"peek_in"}
PROPS = {"stash_item", "portal_exit", "petted", "think", "celebrate_jump", "sad", "talk"}
# Clips whose size legitimately changes (sinking into a portal, being lifted up).
RESIZES = {"portal_exit", "held", "peek_in"}
# Leaning / sniffing poses: feet may shift a little more.
LOOSE_BASELINE = {"petted": 32, "sniff": 32}
SCALE = 4  # analyse at 1/4 size for speed
# Motion checks (mean absolute RGBA difference between frames at 160 x 320).
# Real round-1 clips move 8-17 per step; a repeated frame scores 0.
MIN_MOTION = 3.0
MIN_MOTION_SMALL = 0.8   # tiny minimized-bubble clips only breathe
SAME_FRAME = 0.3         # below this, two frames count as identical
MIN_ICON_DIFFERENCE = 6.0
MIN_POSE_CHANGE = 6.0   # largest pose difference from frame 1, after aligning size/position


def difference(a: Image.Image, b: Image.Image) -> float:
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean[:4]) / 4


def motion_problems(name: str, frames: list[Image.Image]) -> list[str]:
    """Catch clips made of one frame repeated, or two frames flickering back and forth."""
    small = [f.resize((160, 320)) if f.size[1] > 200 else f.resize((96, 96)) for f in frames]
    steps = [difference(a, b) for a, b in zip(small, small[1:])]
    problems = []
    floor = MIN_MOTION_SMALL if frames[0].size[1] <= 200 else MIN_MOTION
    if statistics.mean(steps) < floor:
        problems.append(f"barely moves (mean change {statistics.mean(steps):.2f} per frame, "
                        f"needs {floor}); frames look repeated")
    same = sum(1 for s in steps if s < SAME_FRAME)
    if same >= 2:
        problems.append(f"{same} pairs of consecutive frames are identical")
    if len(small) >= 6:
        period_two = [difference(a, b) for a, b in zip(small, small[2:])]
        if max(period_two) < SAME_FRAME and statistics.mean(steps) >= SAME_FRAME:
            problems.append("only two different frames flickering back and forth")
    # Same drawing just moved or rescaled? Compare poses with position and size removed.
    poses = []
    for frame in frames:
        box = frame.getchannel("A").point(lambda a: 255 if a > 40 else 0).getbbox()
        if box:
            poses.append(frame.crop(box).resize((96, 96)))
    if len(poses) >= 4:
        pose_steps = [difference(a, b) for a, b in zip(poses, poses[1:])]
        pose_change = max(difference(poses[0], p) for p in poses)
        if pose_change < MIN_POSE_CHANGE:
            problems.append(f"the pose never changes (max {pose_change:.2f}); it is one drawing "
                            "moved or scaled, not an animation")
        elif statistics.mean(pose_steps) < MIN_POSE_CHANGE / 3:
            problems.append(f"pose barely changes between frames ({statistics.mean(pose_steps):.2f})")
    return problems


REUSED = 3.0  # aligned-pose difference below which a frame counts as a copy


def pose(frame: Image.Image) -> Image.Image | None:
    box = frame.convert("RGBA").getchannel("A").point(lambda a: 255 if a > 40 else 0).getbbox()
    return frame.convert("RGBA").crop(box).resize((96, 96)) if box else None


def reference_poses(repo: Path) -> list[Image.Image]:
    """Poses from the already-approved GIF clips, to catch frames copied from them."""
    from PIL import ImageSequence
    poses = []
    for gif in sorted((repo / "cerberus" / "assets" / "gifs").glob("*.gif")):
        for frame in ImageSequence.Iterator(Image.open(gif)):
            p = pose(frame)
            if p is not None:
                poses.append(p)
    return poses


def copy_problems(name: str, poses: list[Image.Image], references: list[Image.Image],
                  others: dict[str, list[Image.Image]]) -> list[str]:
    problems = []
    if references and poses:
        copied = sum(1 for p in poses if min(difference(p, r) for r in references) < REUSED)
        if copied * 2 >= len(poses):
            problems.append(f"{copied}/{len(poses)} frames are copies of existing approved clips")
    for other, other_poses in others.items():
        if other == name or not other_poses:
            continue
        same = sum(1 for p in poses if min(difference(p, q) for q in other_poses) < REUSED)
        if same * 2 >= len(poses):
            problems.append(f"{same}/{len(poses)} frames duplicate the {other} clip")
            break
    return problems


def check_icons(folder: Path) -> dict:
    """Icons must be 128 px transparent PNGs and visibly different from each other."""
    files = sorted(folder.glob("*.png"))
    if not files:
        return {}
    images = {f.stem: Image.open(f).convert("RGBA") for f in files}
    report = {}
    for kind, image in images.items():
        problems = []
        if image.size != (128, 128):
            problems.append(f"size {image.size}, expected 128x128")
        if image.getchannel("A").getpixel((0, 0)) != 0:
            problems.append("corner not transparent")
        twins = [other for other, img in images.items()
                 if other != kind and difference(image, img) < MIN_ICON_DIFFERENCE]
        if twins:
            problems.append(f"looks the same as: {', '.join(twins[:6])}"
                            + (" …" if len(twins) > 6 else ""))
        report[kind] = {"pass": not problems, "problems": problems}
    return report


def components(alpha: Image.Image) -> list[tuple[int, tuple[int, int, int, int]]]:
    small = alpha.resize((max(1, alpha.width // SCALE), max(1, alpha.height // SCALE)))
    w, h = small.size
    px = small.load()
    seen = [[False] * w for _ in range(h)]
    found = []
    for y in range(h):
        for x in range(w):
            if px[x, y] > 60 and not seen[y][x]:
                queue = deque([(x, y)])
                seen[y][x] = True
                area, x0, y0, x1, y1 = 0, x, y, x, y
                while queue:
                    cx, cy = queue.popleft()
                    area += 1
                    x0, y0, x1, y1 = min(x0, cx), min(y0, cy), max(x1, cx), max(y1, cy)
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and px[nx, ny] > 60:
                            seen[ny][nx] = True
                            queue.append((nx, ny))
                found.append((area, (x0 * SCALE, y0 * SCALE, (x1 + 1) * SCALE, (y1 + 1) * SCALE)))
    return sorted(found, reverse=True)


def check(name: str, folder: Path) -> dict:
    files = sorted(folder.glob("*.png"))
    problems: list[str] = []
    if len(files) < 4:
        return {"pass": False, "problems": [f"only {len(files)} frames"]}
    frames = [Image.open(f).convert("RGBA") for f in files]
    sizes = {f.size for f in frames}
    if len(sizes) != 1:
        problems.append(f"frames use different canvases: {sorted(sizes)}")
    heights, widths, bottoms = [], [], []
    for index, frame in enumerate(frames, 1):
        alpha = frame.getchannel("A")
        w, h = frame.size
        if any(alpha.getpixel(p) > 0 for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))):
            problems.append(f"frame {index}: corners are not transparent")
        parts = components(alpha)
        if not parts:
            if name != "portal_exit" or index != len(frames):
                problems.append(f"frame {index}: empty")
            continue
        body_area, (x0, y0, x1, y1) = parts[0]
        big = [p for p in parts[1:] if p[0] > body_area * (0.35 if name in PROPS else 0.18)]
        if big:
            problems.append(f"frame {index}: {len(big) + 1} separate bodies (sheet sliced across cells?)")
        if name not in EDGE_OK:
            strip_l = alpha.crop((0, 0, 3, h)).getextrema()[1]
            strip_r = alpha.crop((w - 3, 0, w, h)).getextrema()[1]
            if strip_l > 120 or strip_r > 120:
                problems.append(f"frame {index}: touches the canvas edge (cut-off sliver)")
        heights.append(y1 - y0)
        widths.append(x1 - x0)
        bottoms.append(y1)
    if heights:
        mh, mw = statistics.median(heights), statistics.median(widths)
        for index, (hh, ww) in enumerate(zip(heights, widths), 1):
            if name in RESIZES:
                break
            if abs(hh - mh) > mh * 0.18 or abs(ww - mw) > mw * 0.30:
                problems.append(f"frame {index}: size jumps ({ww}x{hh} vs median {mw:.0f}x{mh:.0f})")
        if name not in AIRBORNE and frames[0].size[1] == 640:
            off = [b for b in bottoms if abs(b - BASELINE) > LOOSE_BASELINE.get(name, 14)]
            if off:
                problems.append(f"feet off the y={BASELINE} baseline in {len(off)} frame(s)")
    if len(sizes) == 1:
        problems = motion_problems(name, frames) + problems
    return {"pass": not problems, "frames": len(frames), "problems": problems[:12]}


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "art/codex")
    report = {}
    folders = [f for f in sorted((root / "frames").glob("*")) if f.is_dir()]
    for folder in folders:
        report[folder.name] = check(folder.name, folder)
    # Copies: frames lifted from approved clips, or one clip duplicated under another name.
    references = reference_poses(Path(__file__).resolve().parents[1])
    all_poses = {f.name: [p for p in (pose(Image.open(x)) for x in sorted(f.glob("*.png"))) if p]
                 for f in folders}
    for name, poses in all_poses.items():
        if name == "wake_up":
            # Must start on the approved fall-asleep pose and end on the approved sitting pose.
            poses = poses[1:-1]
        found = copy_problems(name, poses, references, all_poses)
        if found:
            report[name]["problems"] = (found + report[name]["problems"])[:12]
            report[name]["pass"] = False
    icons = check_icons(root / "icons")
    (root / "qa_report.json").write_text(
        json.dumps({"animations": report, "icons": icons}, indent=2), encoding="utf-8")
    for name, result in list(report.items()) + [(f"icon {k}", v) for k, v in icons.items()]:
        print(f"{'PASS' if result['pass'] else 'FAIL'}  {name}"
              + ("" if result["pass"] else "  — " + "; ".join(result["problems"][:3])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
