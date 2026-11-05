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

from PIL import Image

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
    return {"pass": not problems, "frames": len(frames), "problems": problems[:12]}


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "art/codex")
    report = {}
    for folder in sorted((root / "frames").glob("*")):
        if folder.is_dir():
            report[folder.name] = check(folder.name, folder)
    (root / "qa_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for name, result in report.items():
        print(f"{'PASS' if result['pass'] else 'FAIL'}  {name}"
              + ("" if result["pass"] else "  — " + "; ".join(result["problems"][:3])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
