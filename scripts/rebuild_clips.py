"""Rebuild every generated clip consistently and register the ones that pass QA.

Usage: python scripts/rebuild_clips.py

1. Sheets in art/codex/sheets/<name>_sheet.png (round 4, reference-matched) and accepted
   frame folders in art/codex/frames/<name>/ are normalised with scripts/process_art.py into
   art/codex/processed/frames/<name>/ (same size as idle, feet pinned, soft edges).
2. scripts/qa_codex_art.py runs on the processed frames.
3. scripts/import_codex_art.py copies passing clips into cerberus/assets/clips and the pack.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CODEX = REPO / "art" / "codex"
OUT = CODEX / "processed"
PY = sys.executable
# Accepted round-1 clips (frames) and round-4 items (sheets). Rejected rounds are never used.
ROUND1 = ["wake_up", "held", "petted", "sad", "talk", "think", "sniff", "portal_exit", "stash_item"]
ROUND4 = ["walk", "turn_around", "sit_to_run", "run_to_sit", "mini_curl", "yawn", "scratch_ear",
          "heads_argue", "howl", "chase_tail", "celebrate_jump", "peek_in"]
TIMING = {  # frame_ms, loop
    "walk": (120, True), "turn_around": (110, False), "sit_to_run": (90, False),
    "run_to_sit": (100, False), "mini_curl": (180, True), "yawn": (130, False),
    "scratch_ear": (110, False), "heads_argue": (120, False), "howl": (140, False),
    "chase_tail": (90, True), "celebrate_jump": (100, False), "peek_in": (120, False),
}


def run(*args: str) -> int:
    return subprocess.call([PY, "-I", *args], cwd=REPO)


def verified_round4() -> set[str]:
    """Round-4 sheets whose provenance checks out (new generation made during round 4)."""
    run("scripts/verify_codex_provenance.py", str(CODEX), str(CODEX / ".round4_start"))
    try:
        report = json.loads((CODEX / "provenance_report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {name for name, problems in report.get("items", {}).items() if not problems}


def drop_unaccepted(accepted: set[str]) -> None:
    """Remove pack states and clip folders of generated clips that did not pass this time."""
    pack_path = REPO / "cerberus" / "assets" / "animation-pack.json"
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    generated = set(ROUND1) | set(ROUND4)
    targets = {"wake_up": ["wake", "rouse"], "walk": ["walk"]}
    for name in generated - accepted:
        for state in targets.get(name, [name]):
            entry = pack["states"].get(state)
            if entry and any(str(f).startswith(f"clips/{name}/") for f in entry.get("frames", [])):
                del pack["states"][state]
                print(f"removed from pack: {state}")
        folder = REPO / "cerberus" / "assets" / "clips" / name
        if folder.is_dir():
            for f in folder.glob("*.png"):
                f.unlink()
            folder.rmdir()
    if "walk" not in accepted and "walk" not in pack["states"]:
        # Fall back to the slowed-down run until a real walk passes.
        run_entry = dict(pack["states"]["leave"])
        run_entry["fps"] = 6
        pack["states"]["walk"] = run_entry
    if "wake_up" not in accepted:
        for state in ("wake", "rouse"):
            if state not in pack["states"]:
                sleep = dict(pack["states"]["sleep"])
                sleep.update({"reverse": True, "fps": 7, "loop": False})
                sleep.pop("loop_from", None)
                pack["states"][state] = sleep
    pack_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    meta = {}
    try:
        meta = json.loads((CODEX / "manifest.json").read_text(encoding="utf-8")).get("animations", {})
    except (OSError, ValueError):
        pass
    done = {}
    for name in ROUND1:
        source = CODEX / "frames" / name
        if source.is_dir() and run("scripts/process_art.py", "frames", str(source),
                                   str(OUT / "frames" / name), name) == 0:
            done[name] = {"frame_ms": meta.get(name, {}).get("frame_ms", 110),
                          "loop": meta.get(name, {}).get("loop", False)}
    verified = verified_round4()
    for name in ROUND4:
        sheet = CODEX / "sheets" / f"{name}_sheet.png"
        if name not in verified:
            continue  # only sheets proven to be new, reference-matched generations
        if sheet.is_file() and run("scripts/process_art.py", "sheet", str(sheet),
                                   str(OUT / "frames" / name), name) == 0:
            frame_ms, loop = TIMING[name]
            done[name] = {"frame_ms": frame_ms, "loop": loop}
    # Start clean so stale processed clips from older runs can never be imported.
    for folder in (OUT / "frames").glob("*"):
        if folder.is_dir() and folder.name not in done:
            for f in folder.glob("*.png"):
                f.unlink()
            folder.rmdir()
    (OUT / "manifest.json").write_text(json.dumps({"animations": done}, indent=2), encoding="utf-8")
    icons_dir = OUT / "icons"
    for old in icons_dir.glob("*.png"):
        old.unlink()
    for sheet_name in ("icons_a", "icons_b"):
        sheet = CODEX / "sheets" / f"{sheet_name}_sheet.png"
        if sheet_name in verified and sheet.is_file():
            run("scripts/process_art.py", "icons", str(sheet), str(icons_dir), sheet_name)
    run("scripts/qa_codex_art.py", str(OUT))
    status = run("scripts/import_codex_art.py", str(OUT))
    qa = json.loads((OUT / "qa_report.json").read_text(encoding="utf-8"))["animations"]
    drop_unaccepted({name for name, r in qa.items() if r.get("pass")})
    return status


if __name__ == "__main__":
    raise SystemExit(main())
