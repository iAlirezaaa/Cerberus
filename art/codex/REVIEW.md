# Review of Codex-generated art

Checked with `scripts/qa_codex_art.py` (shape, baseline, real motion, pose change, copies of
approved frames, duplicate clips, distinct icons) and by eye. Codex's own `manifest.json` /
`README.md` are not trusted as a source of truth and are not committed.

## Accepted (round 1) — in `cerberus/assets/clips/`

`wake_up`, `held`, `petted`, `sad`, `talk`, `think`, `sniff`, `portal_exit`, `stash_item`.
Each is a real, reference-matched animation. `held` and `petted` include a drawn human hand.

## Rejected

| clip / asset | round | problem |
| --- | --- | --- |
| `walk`, `turn_around`, `sit_to_run`, `run_to_sit` | 1 | sprite sheets sliced on the wrong grid: two dogs per frame, edge slivers |
| same four | 2 | "fixed" by repeating one existing sitting frame (no motion at all) |
| `yawn`, `scratch_ear`, `heads_argue`, `peek_in` | 2 | one existing frame repeated |
| `howl`, `chase_tail`, `celebrate_jump` | 2 | existing idle/bark frames cycled; chase_tail and celebrate_jump are the same clip |
| `mini_curl`, `mini_wake` | 2 | the sitting pose scaled down, not curled; the two clips are identical |
| all 16 icons | 2 | the same plain document drawn in code for every kind |

Round 2's log shows a single image-generation call (the yawn sheet); everything else was
derived by a script that was deleted afterwards, while the report claimed the work was done.

## Round 3 (strict rules)

Codex followed the honesty rules this time: one genuine new generation (verified by
`scripts/verify_codex_provenance.py`: the file exists in `generated_images`, was created during the
round and matches the saved sheet), then it stopped after the first item and said so. The result is
still rejected: the `walk` sheet shows a lean, realistic, muted-colour wolf facing **left** — not the
chunky ember Cerberus with the Greek-key collar and Ψ medallion — so it fails on identity, not just
on slicing. Nothing from round 3 is imported.

## Still needed

Real animations for the rejected clips and 16 distinct item icons. The app's engine already
plays each clip as soon as it passes QA and is imported (`scripts/import_codex_art.py`).
