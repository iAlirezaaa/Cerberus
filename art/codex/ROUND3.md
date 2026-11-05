# Round 3 — strict rules

Round 2 was rejected: only one image was generated, and every other "clip" was built from copies
of existing frames (repeated, shifted, rescaled or cycled), one clip was saved under two names, and
the 16 icons were one document drawn in code. See `art/codex/REVIEW.md`. Read `BRIEF.md` for the
character, canvas and file formats; they are unchanged.

## Hard rules (breaking any one rejects the item)

1. **Every animation gets its own new image-generation call** that produces a sprite sheet showing
   the new poses. Every icon sheet is a new generation too. No exceptions.
2. **Never reuse pixels** from `cerberus/assets/`, from other clips, or from earlier rounds — not
   copied, shifted, scaled, flipped, recoloured or cycled. Reference images are for *style only*.
3. **Never draw characters or icons with code** (PIL/Qt shapes, text, gradients). Code may only slice,
   align, trim and save what the image tool generated.
4. **Keep everything you used.** Do not delete helper scripts. Save each generated sheet unchanged as
   `art/codex/sheets/<name>_sheet.png`, and record it in `art/codex/provenance.json`:
   `{"<name>": {"generated_file": "<full path under C:\\Users\\Raven\\.codex\\generated_images>",
   "prompt": "<the prompt you used>"}}`. The reviewer checks that these files exist and were created
   during this run.
5. **Be honest.** If image generation fails, is unavailable or hits a limit, stop that item, mark it
   `"status": "skipped"` with the exact reason, and say so in your final message. A skipped item is
   fine; a faked one is not.

## How to slice without the round-1 bug (two dogs per frame)

Ask the image tool for a **single horizontal row** (or a 4 × 2 grid with very wide empty gutters)
of separate, non-overlapping poses on a transparent or flat background. Then find each character by
**connected components of the alpha channel**, not by a fixed grid: take the largest blobs left to
right, crop each, and place it centred on a 320 × 640 canvas with feet on y = 490 (keep scale equal
across frames). Remove the background to real alpha if needed.

## Work order (stop cleanly at any point; partial results are fine)

1. `walk` (8, loop) — calm walking cycle, legs visibly alternating.
2. `turn_around` (8) — sitting facing right → three-quarter → facing left, same scale throughout.
3. `sit_to_run` (6), `run_to_sit` (6).
4. Icons: two generations, each a sheet of 8 distinct 128 × 128 icons in the ember style, then sliced:
   sheet A `text, link, image, pdf, document, spreadsheet, presentation, archive`;
   sheet B `code, audio, video, app, font, email, model3d, file`. Each icon must clearly show its
   kind (a link chain, a picture, "PDF" on a page, a table grid, a slide, a zip/box, `</>`,
   a music note, a play button/film, a gear or window, "Aa", an envelope, a cube, a blank page).
   PNG only this round; skip the animated GIF icons.
5. `mini_curl` (96 × 96, 8, loop) — curled up in a ball, asleep, breathing.
6. `yawn`, `scratch_ear`, `chase_tail`, `heads_argue`, `howl`, `peek_in`, `celebrate_jump`.

## Check before calling anything done

```
D:\Airis\Projects\Pet\Cereberus\.venv\Scripts\python.exe scripts\qa_codex_art.py art\codex
```

The checker now also fails clips that do not move, repeat or flicker between frames, never change
pose, copy approved frames, duplicate another clip, and icons that look alike. Only mark items
`done` when they PASS **and** you have looked at the frames. Do not edit `scripts/` or anything
outside `art/codex/`. Finish with an honest summary in your last message.
