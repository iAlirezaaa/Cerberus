# Cerberus — Engineering Agent Handoff

**Snapshot:** 2026-11-03. **Repository:** https://github.com/iAlirezaaa/Cerberus. **Default branch:** main.
**Read first:** AGENTS.md, LICENSE, docs/LICENSING.md, README.md, docs/PRIVACY.md.

## 1. Mission and intended experience

A small, expressive three-headed mythical dog lives as a transparent on-screen Windows desktop pet. Users intentionally drop text, images, links or files onto it. Cerberus playfully reacts as if it catches the object, stores it locally, and can recall it through the vault search interface. The aesthetic is dark charcoal fur, amber eyes, teal accents, a golden collar/trident and a Hades portal. Standby must be charming, quiet and energy-conscious.

**Do not confuse the concept sheets with shipped character art.** The packaged primary sprite is the generated transparent PNG `cerberus/assets/guardian-ember.png`; `guardian.svg` remains the fallback. The application renders the raster through Qt. The bundled art is one pose with whole-image transforms, not a layered bone rig, 3D model or full frame-by-frame sprite atlas.

## 2. What is already implemented

- Local SQLite database with text and HTTP(S) URLs, copied file attachments and PNG image payloads; deduplication, capped file/text sizes, search via FTS5 where available, JSON metadata export, delete and CLI commands.
- Transparent topmost frameless PySide6 pet, original vector fallback, generated transparent raster character and Qt image caching.
- Drag/drop to pet, pet/reposition via mouse, double-click vault, right-click menu and tray controls.
- MotionMachine transitions: idle -> sleep after roughly 95 seconds; portal -> dash -> catch -> carry -> celebrate -> idle after successful capture; play, wake, alert and guard. Reduced-motion behavior.
- Manual and optional clipboard capture (OFF by default), no cloud account or built-in telemetry.
- Offscreen rendering script that produces state PNGs and an animated GIF.
- Unit tests for core/settings/motion and a Windows Qt offscreen smoke test. Cross-platform core CI and Windows unsigned EXE build workflow exist.

**Validation boundary:** previous CI runs included successful core and Windows offscreen tests. At this snapshot, do NOT infer release-quality Windows desktop behavior, installer testing, native event hooks, an encrypted vault, or current CI status without checking GitHub.

## 3. Not built — do NOT claim otherwise

- Detect any highlighted text in arbitrary applications solely because it became selected, or animate a grab from the text bounding box. This requires OS-specific accessibility APIs and explicit opt-in.
- Native per-pixel input pass-through through transparent margins; currently transparent overlay pixels may intercept mouse clicks.
- Independent 3D/head/paw/tail rig; natural run cycles, nuanced facial expression systems and interactive physics.
- Full document OCR/semantic search, tags/collections, encrypted vault, background indexer, backup restore, signed installer, background auto-updater, paid-license checkout/entitlement verification.
- Real-world end-to-end validation for Windows Explorer/browser/editor drag-drop, multi-monitor mixed-DPI, laptop sleep/resume and performance.

## 4. Architecture and files

- cerberus/vault.py: the sole supported persistence/capture API; GUI-independent.
- cerberus/settings.py: application data path (CERBERUS_HOME override), local opt-in settings.
- cerberus/motion.py: deterministic timing and state transitions; extend this before adding animation special cases to Qt paint.
- cerberus/pet.py: overlay widget, SVG rendering, cursor-based summon and mouse/drop events.
- cerberus/app.py: controller, system tray, opt-in clipboard, vault GUI.
- cerberus/assets/guardian-ember.png: primary generated transparent character artwork.
- cerberus/assets/guardian.svg: original transparent fallback artwork; preserve or layer non-destructively.
- cerberus/assets/animation-pack.json and cerberus/animation_pack.py: bounded local PNG state-frame pack format and parser.
- docs/ANIMATION_PACK.md: version 1 manifest format and resource limits.
- scripts/render_preview.py: generates real, offscreen Qt frames.
- tests/test_vault.py, tests/test_motion.py, tests/test_settings.py, tests/test_gui_smoke.py.
- .github/workflows/ci.yml and windows-build.yml.

**Key boundaries:** core must not depend on Qt, no capture source can bypass vault validation, do not lose source data, keep animation hot path nonblocking and use existing state machine as the source of truth.

## 5. Reproduce, build and check

~~~bash
python -m pip install -e ".[gui]"
python -m compileall -q cerberus tests
python -m unittest discover -s tests -v
python -m cerberus add-text "agent smoke test"
python -m cerberus search "agent smoke"
python -m cerberus.app
~~~

Use a temporary CERBERUS_HOME to avoid writing test data to a person's real vault. In a graphical desktop session, verify drag/drop, tray, click behavior, search and system suspend/resume. For automated Qt checks, set QT_QPA_PLATFORM=offscreen. The rendering preview additionally requires Pillow. For an unsigned .exe, run scripts/build_windows.ps1 on Windows or inspect Windows Build Actions artifacts. A green build does not prove drag/drop and click-through work on physical Windows.

## 6. Next milestones, in execution order

### P0 — desktop integrity and interaction

**Goal:** reliable non-intrusive user experience on Windows.

Acceptance:
- Confirm window visually sits above the desktop in a real logged-in Windows session.
- Drag plaintext, URL, PNG image and a file from Explorer onto the pet; each capture persists once with the expected type.
- Test real browser drag/drop and rejection/error feedback, no loss of original files.
- Hit-testing of transparent edges must not steal unrelated desktop clicks; preserve intentional drop target.
- Test app hide/show, Alt+Tab behavior, tray, high DPI, secondary monitor and sleep/resume.
- Gather actual idle CPU, RAM and animation frame timing. Set budgets based on measurements, not guesses.
- Add regression tests and fix verified defects.

### P1 — character animation production

**Goal:** transform the whole-image mock animation into a polished desktop pet without an expensive continuous renderer.

Acceptance:
- Build optional layered animation assets (head center/left/right, torso, limbs, tail, collar) or a transparent sprite atlas in a documented format.
- States: idle, blink, look, listen, lie-down/sleep, wake, walk/run, jump, portal spawn, catch, chew/save, celebration, failed capture, guard.
- Timeline-driven easing with deterministic tests and 30–60 FPS only for short active actions; low idle update rate.
- Preserve the character identity and transparent background at all supported sizes.
- Reduce-motion mode and pause/guard continue to work; avoid perpetual screen attention or unexplained network activity.
- Provide state PNGs and GIF/video previews built from app assets, not concept sheets substituted as sprites.

### P2 — consent-based selected-text summons

**Goal:** make the requested "selection -> Cerberus enters via Hades gate -> reaches for it" interaction real.

Acceptance:
- New Windows UI Automation adapter behind a visible OFF-by-default toggle; app allow/deny rules and pause control.
- Debounced selection-change event carries only what is needed to position an animation near the bounding rectangle or cursor, with no recording by default.
- Users confirm actual capture by explicit shortcut, click or drop; mere selection does not silently save content.
- Password fields, secure controls and unsupported apps are skipped; permissions and errors are visible.
- No global keylogger, stealth clipboard watcher or screen scraper. Add performance/security tests and document OS limitations.

### P3 — stronger memory

Plan safe document extraction/OCR, richer FTS filters, tags, optional local semantic search, import/restore, corruption handling and encryption-at-rest with migrations. Keep existing vault data compatible.

## 7. Current tradeoffs, performance and privacy

- Python + PySide6 offers a fast UI prototype but no proven optimal RAM footprint. Benchmark before considering Rust/Tauri.
- Content-addressed file copies avoid modifying original data; large and malicious inputs need bounded parsing if new document extraction is added.
- Local-first and no network access are product constraints, not limitations to remove casually.
- Clipboard collection is currently opt-in and can still capture sensitive copied information; exclusion filters would be valuable.
- A source-available commercial license governs new work where rights permit, but historical MIT grants remain. There is no implemented license payment/activation system; do not add a paywall without explicit instructions.

## 8. Definition of done

A work unit is complete only when its source change, regression tests, documentation impact, build/package impact and a verified demonstration are addressed. The agent's final report must include: exact changes; files/commit; CLI/unit/GUI tests performed, including which OS; confirmation that private data was not touched; explicit unverified items; recommended next task. Mark speculative features as TODO rather than shipped.

## 9. Agent continuation prompt

"Read AGENTS.md, docs/AGENT_HANDOFF.md, docs/PRIVACY.md and LICENSE; inspect the current main branch and CI first. Improve the highest-priority unverified Windows desktop interaction issue, preserving the existing SQLite schema, transparent Cerberus identity, opt-in collection and source-available license. Work in a narrow branch, write tests and update docs. Run available checks, publish the commit/PR, and report exactly what passed and what could not be verified."
