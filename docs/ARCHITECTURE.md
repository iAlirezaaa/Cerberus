# Cerberus architecture

## Goal

Build a desktop-native-feeling information companion that is delightful when active and almost invisible when idle. It must be local-first, useful without subscriptions, scriptable, testable, and modular.

## MVP components

- **Capture adapters:** Qt drag/drop for text, URLs and files; explicit clipboard capture; CLI commands. All adapters normalize inputs through Vault.
- **Storage core:** Python standard library, SQLite WAL, FTS5 external-content search with LIKE fallback, content-addressed file copies. No Qt import in the core.
- **Desktop shell:** PySide6 frameless translucent topmost window, transparent PNG mascot and SVG fallback, optional bounded PNG frame packs, time-limited animation, tray controls and branded searchable archive UI.
- **Preferences:** JSON under user app data. Clipboard capture OFF by default.
- **Interface:** Human-oriented GUI and machine-oriented CLI share one database format.

## Event flow

User drag or explicit copy action -> validate type/size -> compute hash -> deduplicate -> copy/persist locally -> signal animated capture -> retrieve via GUI/CLI.

## Important invariants

1. Never move or alter a source file.
2. Never monitor keyboard, accessibility, clipboard or screen without explicit user choice.
3. Capture validation lives in the core, not individual frontends.
4. Idle pet refresh is intentionally throttled; fast redraw happens only during animation.
5. GUI failure cannot silently corrupt or erase the memory vault.
6. Never auto-run, auto-open or execute dropped files.

## Limitations / risks

- Arbitrary text selection in other apps is **not** detectable with Qt alone; true select-trigger animation is not implemented yet. Per-OS accessibility monitoring must be explicitly enabled, and saving should still require consent.
- Transparent margins still may receive pointer clicks; pixel-level input hit testing requires a native adapter.
- Imported files are not text-extracted. Search includes names, stored texts and URLs.
- The local vault is not encrypted at rest; do not store credentials.
- Archive image previews read local image files only and reject dimensions above a fixed pixel budget before decoding.
- Actual Windows/macOS/Linux GUI runs and packaging remain to be validated.
- A Python/Qt GUI has a larger baseline memory footprint than an optimized native Rust app; benchmark before rewriting.

## Future boundaries

Keep the vault API stable while adding OS-specific window hit testing, Windows UI Automation, macOS Accessibility, Linux AT-SPI, animation sprite packs, optional OCR and embeddings, a browser extension, encrypted storage and integrations with knowledge systems.

A future Rust/Tauri shell could replace PySide6 without replacing the data model, provided schema migrations and measurements justify it.

The PNG frame-pack manifest is documented in [ANIMATION_PACK.md](ANIMATION_PACK.md). Assets are local, preloaded before animation, and bounded by per-file and total decoded-pixel limits. The currently bundled character is a single pose animated with whole-image transforms; authored frame sequences and independently animated body parts remain future work.

## Acceptance gates

Core unit tests across Windows/macOS/Linux, GUI smoke tests in a real desktop session, capture regression tests across Explorer/browsers/editors, app exclusion tests, accessibility checks, 10k/100k-item search benchmarks, disk-failure recovery and signed release smoke tests.
