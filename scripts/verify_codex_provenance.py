"""Check that generated art really came from new image-generation calls.

Usage: python scripts/verify_codex_provenance.py [art/codex] [start-marker-file]

For each entry in art/codex/provenance.json: the generated file must exist under
~/.codex/generated_images, be newer than the start marker, and the saved sheet
art/codex/sheets/<name>_sheet.png must be that image (same size, near-identical pixels).
Also reports how many images were generated since the marker in total.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

GENERATED = Path.home() / ".codex" / "generated_images"


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "art/codex")
    marker = Path(sys.argv[2]) if len(sys.argv) > 2 else root / ".round3_start"
    since = marker.stat().st_mtime
    new_files = [p for p in GENERATED.rglob("*") if p.is_file() and p.stat().st_mtime > since]
    print(f"images generated since {marker.name}: {len(new_files)}")
    try:
        # utf-8-sig: PowerShell writes JSON with a byte-order mark.
        provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        print("provenance.json missing or invalid")
        return 1
    used: dict[str, str] = {}
    results = {}
    for name, entry in sorted(provenance.items()):
        problems = []
        source = Path(str(entry.get("generated_file", "")))
        sheet = root / "sheets" / f"{name}_sheet.png"
        if not source.is_file():
            problems.append("generated file does not exist")
        else:
            try:
                source.resolve().relative_to(GENERATED.resolve())
            except ValueError:
                problems.append("generated file is not in the Codex generated_images folder")
            if source.stat().st_mtime <= since:
                problems.append("generated before this round started")
            key = str(source.resolve()).lower()
            if key in used:
                problems.append(f"same generated image as {used[key]}")
            used[key] = name
            if sheet.is_file():
                a = Image.open(source).convert("RGBA")
                b = Image.open(sheet).convert("RGBA")
                if a.size != b.size:
                    problems.append(f"sheet size {b.size} differs from generated image {a.size}")
                else:
                    diff = sum(ImageStat.Stat(ImageChops.difference(
                        a.convert("RGB").resize((256, 256)),
                        b.convert("RGB").resize((256, 256)))).mean) / 3
                    if diff > 12:
                        problems.append(f"sheet is not the generated image (difference {diff:.1f})")
            else:
                problems.append("saved sheet missing")
        results[name] = problems
        print(f"{'OK  ' if not problems else 'BAD '} {name}" + ("" if not problems else "  — " + "; ".join(problems)))
    (root / "provenance_report.json").write_text(json.dumps(
        {"generated_since_start": len(new_files), "items": results}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
