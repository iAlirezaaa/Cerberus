# AGENTS.md — Mandatory guide for coding agents

Read this file FIRST before editing any Cerberus code. Then read docs/AGENT_HANDOFF.md, README.md, docs/ARCHITECTURE.md, docs/PRIVACY.md, LICENSE and docs/ROADMAP.md. This guide applies throughout the repository unless a more specific AGENTS.md is added.

## Product contract

Cerberus is an animated, local-first, three-headed Hades-inspired desktop guardian. A user feeds it text, a URL, a file or an image; it makes a playful capture animation and stores the information in a searchable private vault. It is an actual on-screen desktop widget, not just concept art. Target native Windows first; preserve macOS/Linux compatibility.

The default experience must be safe, easy to turn off and low overhead at idle. There is no hidden data collection, sign-in, telemetry or required cloud service.

## Start-of-task sequence

1. Read the current default branch HEAD and inspect relevant files; do not assume this handoff describes newer commits.
2. Check open issues, the roadmap, current CI and latest failures before choosing work. Avoid duplicates.
3. State a narrow goal and acceptance criteria. Preserve unrelated files and user data.
4. Prefer a feature branch and PR for risky refactors; make small commits with useful messages. Never force-push the default branch.
5. Run focused tests, the complete core suite and, for GUI changes, Qt offscreen smoke tests and preview rendering.
6. Update tests, README, changelog, licensing notes or roadmap as appropriate. Report exact commit, tests actually run and remaining limitations.

## Repository map

- cerberus/vault.py — Qt-independent SQLite vault, capture validation, search, file copies, dedupe, deletion and JSON export.
- cerberus/settings.py — per-user storage directory, preferences; clipboard ingestion defaults OFF.
- cerberus/cli.py and cerberus/__main__.py — scriptable core.
- cerberus/motion.py — time-based, deterministic animation state machine.
- cerberus/pet.py — transparent frameless Qt desktop overlay, bundled SVG rendering, drag/drop, mouse interaction and visual effects.
- cerberus/assets/guardian.svg — ORIGINAL vector mascot used by the real desktop widget.
- cerberus/app.py — search window, clipboard opt-in, tray menu and controller.
- tests/ — vault, settings, motion and Qt offscreen tests.
- scripts/render_preview.py — offscreen state PNG and GIF renderer (Pillow required).
- scripts/build_windows.ps1 and .github/workflows/windows-build.yml — unsigned Windows packaging.
- docs/ — architecture, privacy, roadmap, licensing and agent handoff.

## Commands

Windows PowerShell:
~~~powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[gui]"
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python -m cerberus --help
.venv\Scripts\python -m cerberus.app
~~~

Linux/macOS:
~~~bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[gui]"
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m cerberus --help
.venv/bin/python -m cerberus.app
~~~

Optional offscreen preview:
~~~bash
python -m pip install Pillow
QT_QPA_PLATFORM=offscreen python scripts/render_preview.py
~~~
On Windows, set QT_QPA_PLATFORM=offscreen with PowerShell's env syntax first. CI runs core tests on Windows/macOS/Linux and an offscreen GUI smoke/preview job on Windows. An offscreen pass is NOT proof of real desktop behavior.

## Immutable quality and security rules

- Core storage code must NOT import Qt; UI must call the vault API instead of writing directly to SQLite.
- Never delete/move/execute the original dropped file. Copies are content-addressed; enforce limits, validate URLs and guard unsafe paths.
- Do not silently monitor clipboard, keyboard, screen, selection, browsing or accessibility APIs. Any new collection feature MUST default OFF, be explicitly consented to, show state and support immediate pause/revoke.
- Selecting text in arbitrary third-party apps is NOT implemented yet. Never say it is until a consented OS adapter and integration tests exist.
- Never silently upload captured data or introduce network dependencies into the core.
- No user secrets in fixtures, logs or screenshots. The current vault is NOT encrypted. Do not claim secure-at-rest storage.
- Respect reduced motion, low idle CPU, multi-monitor constraints, ordinary taskbar/window interactions and correct drag/drop acceptance.
- Be honest about native limitations: transparent margins currently lack true pixel-perfect click-through; self-rendered motion is NOT a skeletal/3D rig.
- Preserve the three-head silhouette and original asset rights. Do not copy proprietary artwork from other games or desktop pet projects.
- Do not change the project license without explicit repository-owner direction. The current revision uses Apache-2.0; retain third-party notices, asset provenance and historical grants for earlier MIT/custom-license revisions. Consult LICENSE, NOTICE and docs/LICENSING.md. Do not add telemetry, a paid API requirement, pricing or commerce integration without authorization.

## Coding / testing expectations

Prefer standard-library core code, type hints, bounded I/O, deterministic state tests and incremental patches. Use temporary directories and isolated CERBERUS_HOME for tests. Unit test duplicate capture, file non-destruction, Unicode search, bad input, settings default privacy and transitions between idle, sleep, portal, dash, catch and celebration. Changes to Qt drawing require rendering previews; compare against the approved guardian SVG and inspect actual PNGs. Avoid introducing blocking I/O into the paint or animation path.

## Near-term priorities

P0: Real Windows usability validation (drop behavior, click-through, taskbar, DPI, multiple monitors), crash logging without private data and baseline CPU/RAM measurement.

P1: Separate layered head/limb/tail animation, animation atlas and snappy run/portal/catch sequences with reduced-motion fallback; improve idle and standby behavior.

P2: Opt-in selection detector using Windows UI Automation, with a visible privacy control. Trigger an animation near the selected area; **saving must remain a separate explicit gesture**.

P3: Better retrieval, OCR, safe parsers, import/restore, encryption and optional knowledge base integrations.

See docs/AGENT_HANDOFF.md for scope, acceptance checks and explicit known gaps.

## Completion report format

Summarize: Changed / Why / Tests run + results / Commit or PR URL / Known failures & risks / Next best task. Distinguish implemented code, CI results and real-device verification. Do not write "perfect" or "production-ready" without evidence.

### Animation asset handoff (2026-11-03)

- The user-approved generated GIFs, all 16 RGBA PNG frames, two original sheets and five concept sheets now live in `assets/animations/` and `assets/concepts/`. The GIF alpha issue was corrected; they contain transparent background pixels.
- `assets/animations/animation-pack.json` is an **optional** v1 frame-pack compatible with `CERBERUS_ASSET_PACK`; do NOT replace the app's current default pack without real desktop QA. These sequence frames carry some generated smoke/glow edge artifacts; review on both light and dark desktops.
- For production animation prefer per-frame PNG alpha over GIF one-bit transparency. Validate loop behavior, silhouette stability, timing, memory and cursor hit testing. Refer to `assets/animations/README.md`.
- Never substitute generated concept sheets for real alpha sprites; preserve source PNG frames. The ZIP is built from tracked sources using `scripts/package_animation_assets.py` (avoid committing duplicate ZIP binaries to git).
