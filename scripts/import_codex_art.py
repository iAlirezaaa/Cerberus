"""Copy generated art that passed the QA gate into the app and register it in the pack.

Usage: python scripts/import_codex_art.py [art/codex]   (run scripts/qa_codex_art.py first)

* Clips: art/codex/frames/<name>/NN.png -> cerberus/assets/clips/<name>/NN.png, added to
  cerberus/assets/animation-pack.json as anchored PNG lists (soft alpha kept).
  `wake_up` drives the wake and rouse phases; `walk` replaces the slowed-down run.
* Icons: art/codex/icons/<kind>.png|.gif -> cerberus/assets/icons/ when 128x128 RGBA.
Anything failing the gate is skipped and listed.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
ASSETS = REPO / "cerberus" / "assets"
PACK = ASSETS / "animation-pack.json"
# Generated clip name -> pack states it drives.
TARGETS = {"wake_up": ["wake", "rouse"], "walk": ["walk"]}
LOOPING = {"walk", "held", "petted", "talk", "think", "sniff", "chase_tail", "mini_curl"}
# Lead-in frames played once before the loop (e.g. being lifted before dangling).
LOOP_FROM = {"held": 3, "petted": 2}
KINDS = ("text", "link", "image", "pdf", "document", "spreadsheet", "presentation", "archive",
         "code", "audio", "video", "app", "font", "email", "model3d", "file")
MAX_ICON_BYTES = 2 * 1024 * 1024


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "art" / "codex"
    qa = json.loads((root / "qa_report.json").read_text(encoding="utf-8"))
    meta = json.loads((root / "manifest.json").read_text(encoding="utf-8")).get("animations", {})
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    imported, skipped = [], []
    for name, result in sorted(qa.items()):
        if not result.get("pass"):
            skipped.append(f"{name}: {'; '.join(result.get('problems', [])[:2])}")
            continue
        source = sorted((root / "frames" / name).glob("*.png"))
        target = ASSETS / "clips" / name
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        names = []
        for index, frame in enumerate(source, 1):
            image = Image.open(frame).convert("RGBA")
            out = target / f"{index:02d}.png"
            image.save(out, optimize=True)
            names.append(f"clips/{name}/{out.name}")
        frame_ms = int(meta.get(name, {}).get("frame_ms", 110))
        loop = bool(meta.get(name, {}).get("loop", name in LOOPING))
        entry = {"frames": names, "fps": round(min(30.0, max(0.5, 1000 / frame_ms)), 2),
                 "loop": loop, "anchored": True}
        if loop and name in LOOP_FROM and LOOP_FROM[name] < len(names):
            entry["loop_from"] = LOOP_FROM[name]
        for state in TARGETS.get(name, [name]):
            pack["states"][state] = dict(entry)
        imported.append(name)
    icons_out = ASSETS / "icons"
    icons_out.mkdir(exist_ok=True)
    icon_done = []
    for kind in KINDS:
        for suffix in (".png", ".gif"):
            source = root / "icons" / f"{kind}{suffix}"
            if not source.is_file() or source.stat().st_size > MAX_ICON_BYTES:
                continue
            with Image.open(source) as image:
                ok = image.size == (128, 128) and (suffix == ".gif" or image.mode == "RGBA")
                if ok and suffix == ".png":
                    ok = image.getchannel("A").getpixel((0, 0)) == 0
            if ok:
                shutil.copy2(source, icons_out / source.name)
                icon_done.append(source.name)
            else:
                skipped.append(f"icon {source.name}: not a transparent 128x128 image")
    PACK.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("imported clips:", ", ".join(imported) or "none")
    print("imported icons:", ", ".join(icon_done) or "none")
    for line in skipped:
        print("skipped:", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
