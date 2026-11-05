"""Write one strict, reference-attached Codex prompt per missing item (round 4)."""
from pathlib import Path

from PIL import Image, ImageSequence

ROOT = Path(__file__).resolve().parent
REF = ROOT / "references"
frames = [f.convert("RGBA") for f in ImageSequence.Iterator(
    Image.open(ROOT.parents[1] / "cerberus" / "assets" / "gifs" / "fall_asleep.gif"))]
frames[-1].save(REF / "fall_asleep_08.png")

SIT = ["idle_breathe_01.png", "idle_breathe_04.png", "bark_01.png"]
RUN = ["run_01.png", "run_03.png", "run_05.png", "run_07.png"]
ITEMS = {
    "walk": ("8 frames, loop. A calm, relaxed WALK cycle (slower than the attached run): legs clearly "
             "alternate step by step, body bobs slightly, tail sways.", RUN + ["idle_breathe_01.png"]),
    "turn_around": ("8 frames, not looping. Sitting facing RIGHT (frame 1 = the attached sitting pose) "
                    "→ turns through a three-quarter front view → sitting facing LEFT (last frame). "
                    "Same size in every frame; front/three-quarter views only, never the back.",
                    SIT + ["idle_look_01.png"]),
    "sit_to_run": ("6 frames, not looping. From the attached sitting pose it gets up and launches into "
                   "the attached run (last frame ≈ run pose).", ["idle_breathe_01.png"] + RUN[:2]),
    "run_to_sit": ("6 frames, not looping. From the attached run pose it slows, skids and sits down "
                   "(last frame ≈ the attached sitting pose).", RUN[:2] + ["idle_breathe_01.png"]),
    "icons_a": ("ICON SHEET: 8 distinct icons in one row, each in the same glowing-ember paper style as "
                "the attached glowing document and scroll (bright orange glow, dark ink, bronze trim). "
                "In order: text (lines of writing), link (chain links), image (picture with mountain and "
                "sun), pdf (page with the word PDF), document (page with a folded corner and paragraphs), "
                "spreadsheet (table grid), presentation (slide with a bar chart on an easel), archive "
                "(zip/box with a zipper). Each must be instantly recognisable at 32 px.",
                ["icon_style_document.png", "icon_style_scroll.png", "carry_file_01.png"]),
    "icons_b": ("ICON SHEET: 8 distinct icons in one row, same glowing-ember paper style as the attached "
                "references. In order: code (</> symbol), audio (music note), video (film strip with "
                "play triangle), app (window with a gear), font (big 'Aa'), email (envelope), model3d "
                "(wireframe cube), file (plain blank page). Each must be recognisable at 32 px.",
                ["icon_style_document.png", "icon_style_scroll.png", "carry_file_01.png"]),
    "mini_curl": ("8 frames, loop, deliver on a 96 x 96 canvas. Cerberus CURLED UP IN A TIGHT BALL asleep, "
                  "all three heads tucked, tail wrapped around, gentle breathing. Close-up, cute.",
                  ["fall_asleep_08.png", "idle_breathe_01.png"]),
    "yawn": ("8 frames, not looping. Sitting; the left head yawns wide, then the middle, then the right "
             "(a contagious yawn), then all settle.", SIT),
    "scratch_ear": ("8 frames, not looping. Sitting; lifts a back paw and scratches behind an ear, happy "
                    "squint, then puts the paw down.", SIT),
    "heads_argue": ("10 frames, not looping. The left and right heads snap and squabble at each other, the "
                    "middle head rolls its eyes, then sighs.", SIT + ["idle_look_01.png"]),
    "howl": ("8 frames, not looping. All three heads lift to the sky and howl, mouths open, then lower.",
             SIT + ["stand_alert_01.png"]),
    "chase_tail": ("10 frames, loop. Spins in a circle chasing its own flaming tail; the body rotates "
                   "visibly around (side, front, other side).", ["idle_breathe_01.png", "run_01.png", "play_orb_01.png"]),
    "celebrate_jump": ("8 frames, not looping. Crouches, then a happy hop with all four paws off the ground, "
                       "lands, with small sparks.", ["idle_breathe_01.png", "run_03.png", "play_orb_01.png"]),
    "peek_in": ("8 frames, not looping. Enters from the RIGHT edge of the canvas: frame 1 only the head "
                "peeking in from the right edge, then it steps fully in and sits (last frame = sitting).",
                SIT[:2] + ["idle_wait_01.png"]),
}

TEMPLATE = """# Round 4 item: `{name}`

You are making ONE item for the Cerberus desktop pet. **The attached images are the exact,
approved character.** Pass these attached images to your image-generation tool as reference
images for the generation, and keep the design identical: same three wolf heads with glowing
diamond runes, charcoal-brown fur with glowing orange lava cracks, amber eyes, bronze Greek-key
collar with the round Ψ trident medallion, flame-tipped tail, chunky cute proportions, same
lighting and colours. **Facing RIGHT** like the references (unless told otherwise below).

## What to make
{description}

## Hard rules
1. Exactly one new image-generation call for the sheet (a second attempt is allowed only if the
   first fails the identity check below). Never reuse, shift, scale, flip or cycle existing pixels,
   and never draw the character or icons with code.
2. Ask for the poses in a single horizontal row with wide empty gutters on a transparent or flat
   background.
3. Save the generated sheet unchanged as `art/codex/sheets/{name}_sheet.png` and add to
   `art/codex/provenance.json` (keep existing entries):
   `"{name}": {{"generated_file": "<full path under C:\\\\Users\\\\Raven\\\\.codex\\\\generated_images>", "prompt": "<prompt>"}}`.
4. Identity check before slicing: compare your sheet with the attached references. If it is not
   clearly the same character (e.g. a lean realistic wolf, wrong colours, no collar/medallion,
   facing the wrong way), regenerate once; if still wrong, mark it skipped and stop.
5. **Do not slice or post-process.** The reviewer removes the background and slices the sheet with
   the project's own tool. A plain light background (even a checkerboard) is fine; keep the poses
   well separated and the whole character inside the image{canvas_note}.
6. Record the item in `art/codex/manifest.json` as `"sheet_ready"` (or `"skipped"` with the reason).
7. Do not edit `scripts/` or anything outside `art/codex/`. If image generation fails or hits a
   limit, stop and say so. End with one honest paragraph: what you generated and any problems.
"""

(ROOT / "items").mkdir(exist_ok=True)
lines = []
for name, (description, refs) in ITEMS.items():
    note = " (this one is a close-up: the curled ball fills each pose)" if name == "mini_curl" else ""
    (ROOT / "items" / f"{name}.md").write_text(
        TEMPLATE.format(name=name, description=description, canvas_note=note), encoding="utf-8")
    images = " ".join(f'-i "art/codex/references/{ref}"' for ref in refs)
    lines.append(f"{name}|{images}")
(ROOT / "items" / "queue.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(len(ITEMS), "item prompts written")
