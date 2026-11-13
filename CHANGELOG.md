## 2026-11-14 — Four underworld companions

- Replaced previous mascot assets with the supplied Ghost, Hades, Charon and Cerberus identities.
- Added four transparent humorous character GIFs and their 64 PNG source frames.
- Added persistent live character selection, refreshed tray/bubble artwork, and kept capture offerings visible for each identity.
- Updated artwork packaging, regression tests and previews. All assets load locally without a generation service.

# Changelog

## Unreleased — vault previews, minimized mode, item icons, generated clips

- **Vault previews:** images, animated GIF/WebP, PDF page 1 (with page count), the first 64 KB of text and code files, and a kind icon for everything else. Previews are decoded from an in-memory copy, so the stored file is never locked. The real type is sniffed from the bytes rather than taken from the file name. Saved text is always shown as plain text. Programs and scripts are never opened from the vault; they are shown in their folder instead.
- **Vault location in the archive window:** "Stored in" strip with Open folder and Change… (same copy-don't-move flow as Settings).
- **Minimized mode:** a – button on hover, a single tray click, the menu item or the shortcut (new action "Minimize / restore") turns Cerberus into a small bubble where it stood. The bubble restores on click, moves by dragging, and **saves anything dropped on it without restoring**. It is a still image unless hovered, costs no CPU, and is remembered across restarts.
- **Item icons:** a 16-kind classification (text, link, image, PDF, document, spreadsheet, presentation, archive, code, audio, video, app, font, email, 3D model, file) used in the vault list and previews, with designed icons when bundled.
- **Clip-ready engine:** optional clips (wake-up, sit/stand bridges, turn-around, held, petted, sad, portal exit, stash item, talk, think, sniff, yawn, scratch ear, chase tail, heads argue, night howl, peek-in, celebrate jump, mini curl) play automatically when present in the pack. Phase timings follow each clip's real length. Soft-alpha PNG frame lists can stand on the ground line like GIFs.
- `scripts/qa_codex_art.py`: an automatic quality gate for generated frames (one body per frame, no edge slivers, stable scale, baseline).
- Fixes: deleting an item removes the stored copy before its record, and reports a locked file instead of leaving an orphan.

## Unreleased — a livelier guardian, settings window and custom shortcuts

- **Alive on screen:** Cerberus strolls along the screen (occasionally with zoomies), turns toward the cursor, cross-fades between clips, kicks up dust when running, floats "z"s while asleep and hearts when petted.
- **Talks and thinks:** speech and thought bubbles with playful lines in English and Persian (فارسی), time-of-day greetings, reactions to petting, dragging, captures and milestones. Chat level Silent / Quiet / Normal / Chatty.
- **Shows what it caught:** the scroll and document in the catch/carry clips now display the real item: a text, link or image thumbnail, or the file's own system icon plus its extension.
- **Smoother transitions:** waking up is the fall-asleep clip played backwards; it now gets up before running off-screen.
- **Send away / call back:** a hover button on Cerberus sends it away; while away a small portal button stays docked at the screen edge — click it to call Cerberus back.
- **Custom shortcuts:** choose the mouse gesture (Left + Right, Ctrl + Middle, side Back/Forward button, or off) and any keyboard shortcut (default Ctrl+Alt+C), and whether it summons or toggles. On Windows the gesture's clicks are swallowed by a low-level hook, so left+right no longer opens the app's right-click menu.
- **Settings window:** shows exactly where memories, copied files and settings are stored, with Open folder / Change location (copies the vault, keeping the original) / Use default location, plus all companion, nap, shortcut and capture options.
- Tray icon now uses Cerberus's own heads.

## Unreleased — animated GIF character, wander-off and left+right summon

- The desktop pet now plays 13 authored transparent GIF clips (bundled in `cerberus/assets/gifs/`) instead of single static poses: idle, look-around, tail wag, sit-and-wait, bark, fall asleep, stand alert, Hades portal entrance, run, catch scroll, carry file, data snack and play with orb.
- Idle rotates between the idle clips; GIF frames are decoded once, cropped to the character and drawn on a shared ground line at a consistent scale.
- After a period without interaction (default 180 s, tray toggle "Wander off screen when unused") Cerberus runs off the nearest screen edge and hides; its animation timer stops while away.
- Pressing the left and right mouse buttons together anywhere (Windows) summons Cerberus back through the portal at the cursor. Only the two button states are sampled; tray toggle "Summon with left + right click together". Tray "Summon" and "Show / hide" also bring it back.
- Animation-pack manifests accept `gif` entries with optional `loop_from` and `scale` (version 2); PNG packs keep working.

## Unreleased — Apache-2.0 licensing and maintainer skill

- Applied the official Apache License 2.0 to the current repository revision and added a NOTICE covering attribution, historical grants, marks and third-party components.
- Replaced source-available/paid-use licensing documentation with current Apache-2.0 terms, preserving the grants attached to previously released revisions.
- Added a repository-discoverable Cerberus maintainer skill and updated package license metadata and repository badges.

## Unreleased — branded visual archive

- Reworked the vault window into a dark ember Cerberus archive with live totals, searchable item list, capture detail cards and bounded local image thumbnails.
- Added a manual JSON export action and Qt-independent vault summary statistics.
- Verified archive search, stats and capture details in offscreen GUI and vault tests.

## Unreleased — generated raster character and animation packs

- Added generated alpha-transparent PNG character art as the primary desktop sprite, plus run, carry, sleep and guard poses; retained the original SVG as fallback.
- Added a bounded local animation-pack manifest supporting per-state PNG frames on the deterministic motion timeline.
- Preserved reduced-motion behavior and documented that authored state sequences and independent body-part animation remain future work.

## Unreleased — license and agent operations (2026-11-03)

- Added a repository-wide AGENTS.md, an engineering handoff and a continuation prompt for future coding agents.
- Adopted the prospective Cerberus Personal & Paid Production source-available license for qualifying new revisions/material; personal use is free, business and objectively defined heavy production use require a separate paid written agreement.
- Documented the non-retroactive status of earlier MIT grants, pricing/activation not implemented, licensing FAQ and Persian summary.
- Updated package metadata, README and contributor guidance to avoid misleading MIT/open-source claims.


## 0.2.0-dev — screen-ready guardian character (2026-11-03)

### Added
- Original alpha-transparent three-headed SVG mascot bundled as a packaged GUI resource.
- Cached high-resolution sprite render, scalable on-screen pet with 3 tray size presets.
- Animated Hades portal entrance, dash/run, paper-catch, celebration, idle breathing, wake-up and playful pat response.
- Automatic sleepy standby after roughly 95 seconds without pet interaction; tray sleep, guard, wake and play.
- Cross-platform deterministic animation state machine with tests and reduced-motion option.
- On-screen placement near desktop bottom-right, bounded dragging, plus a test-time PNG/GIF sprite preview exporter.

### Notes
- This is a **2D vector sprite with procedural transforms**, not a skeletal 3D rig or independently articulated animation set.
- Selection-only triggers and pixel-perfect input pass-through remain future work. Run real-desktop GUI tests before production use.

## 0.1.0 — initial development snapshot (2026-11-03)

### Added
- Three-headed procedurally drawn desktop pet with Hades portal/catch animation.
- Local-first SQLite vault, full-text search when FTS5 is available, and duplicate detection.
- Text, URL, file and image capture (with limits and non-destructive file copies).
- Desktop tray controls, searchable vault window, optional copied-item capture.
- Scriptable CLI, JSON metadata export and settings.
- Windows/macOS/Linux core tests and Windows offscreen GUI smoke test.
- Original SVG identity, roadmap, architecture and privacy documentation.
- Optional Windows executable packaging workflow.

### Known limitations
- Native selection-triggered capture/animation is not yet implemented; opt-in clipboard observation after copying is the nearest current equivalent.
- Pixel-perfect click-through, real-desktop GUI validation, installers, encryption, OCR and semantic indexing remain future work.
- Unsigned Windows executable artifacts are experimental test builds, not verified releases.
