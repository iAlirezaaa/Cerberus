# Cerberus art brief for Codex

You are producing animation art for **Cerberus**, a three-headed ember-and-lava hellhound desktop pet
(Python + Qt app in this repository). Use your image generation tool. Work through the list **in
priority order** and **update `art/codex/manifest.json` after every finished item**, so partial
results are usable even if you stop early.

## Match the existing character exactly

Reference art (study several frames before generating anything):

- `cerberus/assets/gifs/idle_breathe.gif`, `idle_wait.gif`, `run.gif`, `fall_asleep.gif`,
  `carry_file.gif`, `bark.gif` — the current, approved clips.
- Extract frames with the project's Python, which has Pillow:
  `D:\Airis\Projects\Pet\Cereberus\.venv\Scripts\python.exe`.
- Pass extracted frames as **reference images** to the image tool for every generation.

Character rules: three wolf-like heads (middle head slightly higher, a glowing diamond rune on each
forehead), dark charcoal-brown fur, glowing orange lava cracks and ember edges, glowing amber eyes,
a bronze Greek-key collar with a round **Ψ (trident) medallion**, fluffy flame-tipped tail. Cute,
chunky, chibi proportions. Same rendering style, lighting and colours as the references. **Never
redesign the character.**

## Technical format (every animation)

- Canvas **320 × 640 px**, **fully transparent background** (real alpha, no white or checkerboard).
- Character **faces right**, about **300 px wide**, **feet on the line y = 490** in every frame
  (same scale as `idle_breathe.gif`). Keep the canvas, scale and baseline identical across frames.
- 8 frames unless stated (6–12 allowed). Smooth, loop-safe motion where marked "loop".
- Best method: generate **one sprite sheet per animation** (e.g. 4 × 2 grid of equal cells) using the
  references, then slice, align to the baseline and centre each frame with Python.
- Deliver for each animation `<name>`:
  - `art/codex/frames/<name>/01.png … NN.png` — RGBA PNG frames (keep soft alpha on glows),
  - `art/codex/gifs/<name>.gif` — transparent GIF, loop forever, per-frame delay in ms,
  - `art/codex/sheets/<name>_sheet.png` — the source sheet.
- Quality checks before marking an item done: corner pixels alpha = 0; no leftover background
  colour; feet within ±4 px of y = 490 in every frame; character identity matches references;
  first/last frames match the clip it connects to (see "connects").

## Priority 1 — missing poses and in-betweens (fixes jumps between clips)

| name | frames | loop | what happens | connects |
| --- | --- | --- | --- | --- |
| `wake_up` | 10 | no | lying asleep → big yawn and stretch → sitting upright | starts like last frame of `fall_asleep.gif`, ends like first frame of `idle_breathe.gif` |
| `sit_to_run` | 6 | no | sitting → gets up and launches into a run | `idle_breathe` → `run` |
| `run_to_sit` | 6 | no | running → skids to a stop → sits | `run` → `idle_breathe` |
| `turn_around` | 8 | no | sitting facing right → turns to face left (app mirrors it for the other way) | `idle_breathe` → mirrored `idle_breathe` |
| `walk` | 8 | yes | calm walking cycle (slower, relaxed, not running) | — |
| `held` | 8 | yes | picked up by the scruff like a puppy, legs paddling, tail swishing, surprised faces | — |
| `petted` | 8 | yes | eyes closed, leaning into a head scratch, happy, tail wagging | — |
| `sad` | 8 | no | ears flatten, heads droop, small whimper (used when a capture fails) | ends near `idle_breathe` |
| `portal_exit` | 10 | no | a Hades fire portal opens under it, it hops in and sinks; last frame = empty canvas | starts like `idle_breathe` |
| `stash_item` | 10 | no | holds a glowing orange document, digs a small fiery portal hole and buries it, proud pose | after `carry_file` |
| `talk` | 8 | yes | sitting, the middle head talks (mouth opening/closing), other heads react | — |
| `think` | 8 | yes | head tilt, one paw raised to chin, one head looking up, curious | — |
| `sniff` | 8 | yes | nose low, sniffing toward the right, tail up, curious | — |

## Priority 2 — fun ideas (add personality)

| name | frames | loop | what happens |
| --- | --- | --- | --- |
| `yawn` | 8 | no | one head yawns, then the next, then the third (contagious yawn) |
| `scratch_ear` | 8 | no | sits and scratches an ear with a back paw |
| `chase_tail` | 10 | yes | spins chasing its flaming tail |
| `heads_argue` | 10 | no | left and right heads squabble, middle head rolls its eyes and sighs |
| `howl` | 8 | no | all three heads howl at the sky (night-time) |
| `peek_in` | 8 | no | enters from the RIGHT edge of the canvas: only the front half visible at first, peeks, then steps fully in |
| `celebrate_jump` | 8 | no | happy hop with all four paws off the ground, sparks |

## Priority 3 — minimized mode

- `mini_curl`: **96 × 96 px** canvas, 8 frames, loop — Cerberus curled into a tiny sleeping ball,
  slow breathing, ember glow pulse. Used as the minimized bubble.
- `mini_wake`: 96 × 96, 6 frames — the curled ball pops one head up and blinks.

## Priority 4 — icons for items given to Cerberus

Ember-styled icons that match the character (glowing orange paper/objects, charcoal, bronze,
small lava cracks). For each kind deliver:

- `art/codex/icons/<kind>.png` — 128 × 128 RGBA, transparent, centred, readable at 32 px,
- `art/codex/icons/<kind>.gif` — 128 × 128, 8 frames, loop, subtle (glow pulse or gentle float).

Kinds: `text`, `link`, `image`, `pdf`, `document`, `spreadsheet`, `presentation`, `archive`,
`code`, `audio`, `video`, `app` (installers/executables), `font`, `email`, `model3d`, `file`
(generic unknown).

## manifest.json format

```json
{
  "animations": {
    "wake_up": {"frames": 10, "frame_ms": 110, "loop": false, "canvas": [320, 640],
                "baseline_y": 490, "status": "done", "notes": "..."}
  },
  "icons": {"pdf": {"status": "done"}}
}
```

Use `"status": "done"`, `"needs_review"` (usable but imperfect — say why in notes) or `"skipped"`.
Finish with `art/codex/README.md` summarising what was made and any problems. Do not edit any
file outside `art/codex/`.
