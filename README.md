<div align="center">

# CERBERUS
### The three-headed guardian of your digital memory.

**Catch it. Keep it. Find it.**

An animated, local-first desktop companion that catches text, URLs and files you feed it, then guards them in a searchable vault.

![Cerberus mark](assets/cerberus-mark.svg)

[![CI](https://github.com/iAlirezaaa/Cerberus/actions/workflows/ci.yml/badge.svg)](https://github.com/iAlirezaaa/Cerberus/actions/workflows/ci.yml)

</div>

## What is Cerberus?

Cerberus is a playful desktop pet with a real job: capturing information. Drag text, a link or a file onto the three-headed hellhound. It catches the item, enters a short Hades-portal animation, and saves it into your **local**, searchable memory vault.

Inspired by desktop pets such as Shimeji, Cerberus adds an information capture and retrieval layer rather than just screen decoration.

**Current status: early MVP, not a production release.** Features below are implemented in source; platform-specific GUI behavior still needs device testing.

## Features in this version

- **Three-headed animated desktop pet:** translucent, frameless, always-on-top Qt overlay; custom vector-painted mascot with idle, portal, dash and catch reactions.
- **Feed it by dragging:** text, HTTP(S) links, and local files dropped onto the pet are captured.
- **Portable memory vault:** local SQLite database with FTS5 full-text indexing when available and an indexed fallback; files are **copied**, never moved from their source.
- **Find what it swallowed:** desktop search window and command-line search/list/export/delete commands.
- **Clipboard capture (opt-in only):** disabled by default; when enabled, newly copied clipboard text/URLs can be captured with an animation. **Selecting/highlighting text alone does not trigger capture in this MVP.**
- **System tray controls:** show/hide, open vault, manually feed clipboard, toggle clipboard capture, quit.
- **Safe defaults:** no account, cloud service, analytics, microphone, network upload or hidden clipboard collection. Data stays under your user profile unless you override the data directory.
- **Duplicate detection, capture limits, atomic file writes and unit tests.**

## Quick start

Requires **Python 3.11+**. Desktop GUI requires PySide6. Tested logic is platform-independent; the GUI is primarily targeted at Windows 10/11, with macOS/Linux support to be validated.

```powershell
git clone https://github.com/iAlirezaaa/Cerberus.git
cd Cerberus
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[gui]"
cerberus-desktop
```

On macOS/Linux, activate with `source .venv/bin/activate`.

### Try the vault from a terminal

```bash
python -m cerberus add-text "A thought worth keeping" --title "My note"
python -m cerberus add-url "https://example.org"
python -m cerberus add-file "./notes.pdf"
python -m cerberus search "thought"
python -m cerberus list
python -m cerberus export ./cerberus-export.json
python -m unittest discover -s tests -v
```

Run `python -m cerberus --help` for all commands. Override the data directory with `CERBERUS_HOME`.

## How it works

1. Drop text, URLs or a file **onto Cerberus** (or use the CLI).
2. Cerberus plays a portal/catch reaction and writes the item to the local vault.
3. Double-click the pet or use the tray menu to search and retrieve it.

The global-selection animation described in the original concept will require a separate, **explicitly enabled** OS accessibility integration. Ordinary selection in arbitrary applications is not observable through Qt alone. Clipboard capture works after an actual copy action, never merely because text is highlighted.

## Why this architecture?

The MVP uses a **Python core + PySide6 desktop shell** for fast iteration and a transparent window that accepts native drag-and-drop. Storage, metadata and deduplication live in pure Python with no Qt dependency, so they can be reused later by a native Rust/Tauri shell if performance benchmarks justify migrating.

- **Core:** `cerberus/vault.py` — capture, SQLite, FTS, safe file copies, export.
- **Preferences:** `cerberus/settings.py` — opt-in settings, local profile storage.
- **Pet:** `cerberus/pet.py` — native drag/drop, procedural mascot, animation phases.
- **Desktop:** `cerberus/app.py` — tray, vault search, clipboard integration.
- **CLI:** `cerberus/cli.py` — scriptable memory operations.

See [Architecture](docs/ARCHITECTURE.md), [Roadmap](docs/ROADMAP.md), and [Privacy](docs/PRIVACY.md).

## Safety & privacy

Nothing is uploaded to a server. The local vault is **not encrypted at rest yet**; it inherits the current user's filesystem permissions. Don't use it for secrets or passwords. An export contains text/URLs and file metadata, not copied file bytes. Imported file contents are limited to 50 MiB per item; text to 1 MiB. Data is kept until you delete it. Clipboard watching starts OFF.

## Planned

Native selected-text detection **with explicit user consent**, cursor-relative portal entrances, richer sprite animations, multi-monitor awareness, configurable animation behavior, encrypted vault, OCR, semantic search, browser companion, plugin SDK, optional integration with second-brain systems, packaging and signed releases. Nothing in this paragraph is claimed as shipped.

## Contributing

Issues and pull requests are welcome. Please include reproduction steps and OS details for platform-specific bugs. Run `python -m unittest discover -s tests` before opening a PR.

**License:** [MIT](LICENSE)
