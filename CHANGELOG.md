# Changelog

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
