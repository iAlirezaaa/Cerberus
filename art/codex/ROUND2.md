# Round 2 — fixes first, then the rest of BRIEF.md

Read `art/codex/BRIEF.md` again (same character rules and formats) and `art/codex/qa_report.json`.

## 1. Fix these four clips (they fail the automatic QA)

`walk`, `turn_around`, `sit_to_run`, `run_to_sit`: frames 3–5 each contain **two dogs stacked on top
of each other** and thin slivers from neighbouring cells at the left/right edges. The sprite sheets
were sliced on the wrong grid. Regenerate or re-slice them so that **every frame contains exactly
one complete Cerberus**, nothing touches the canvas edge, the size stays the same from frame to
frame, and the feet stay on y = 490. For `turn_around`, keep the same scale as the other frames
(the last frames were much larger) and show a side/three-quarter turn, not a back view.

## 2. Then do the parts of BRIEF.md that were skipped

Priority 2 (fun ideas), Priority 3 (`mini_curl`, `mini_wake`, 96 × 96) and Priority 4 (all 16 icons,
128 × 128 PNG + GIF). Same deliverable paths and manifest updates as before.

## Check your own work before marking anything done

After each clip run the project's checker and fix anything it reports:

```
D:\Airis\Projects\Pet\Cereberus\.venv\Scripts\python.exe scripts\qa_codex_art.py art\codex
```

Only mark a clip `"status": "done"` when it shows PASS. Also look at the frames yourself: one body per
frame, same character, smooth motion. Update `art/codex/README.md` at the end. Do not edit files
outside `art/codex/`.
