# Development roadmap

The completed boxes describe source-code features, not installer-quality guarantees.

## v0.1 — functional prototype

- [x] Create public repository and project identity
- [x] Standalone local SQLite core, FTS search fallback, deduplication
- [x] Safe file import, text/URL capture, JSON export
- [x] Scriptable CLI
- [x] Frameless transparent three-headed desktop pet
- [x] Original procedural pet art and animated portal/catch state
- [x] Drag and drop, tray menu, vault search UI
- [x] Opt-in clipboard capture, off by default
- [x] Core regression tests and CI definition
- [ ] Confirm Windows GUI functionality in a real user session
- [ ] Measure real idle CPU, RAM, responsiveness

## v0.2 — playful desktop pet

- [x] Original transparent three-headed SVG fallback and generated transparent PNG primary sprite
- [x] Generated transparent poses for run, carry, sleep and guard states
- [x] Bounded, local PNG animation-pack manifest and state-frame playback support
- [x] Procedural sprite transforms: idle breathing, portal, dash, catch, celebrate, play, wake, sleep
- [x] Tray wake/play/sleep/guard controls, three sizes and reduced-motion mode
- [x] Branded searchable archive with live totals, item details, bounded local image previews and manual JSON export
- [ ] Authored state frame sequences and full layered sprite atlas: articulated run, leap, chew, independent heads/legs/tail, fail
- [ ] Pixel-level click-through around mascot and multi-monitor HiDPI
- [ ] Cursor follow, idle curiosity, random reactions, custom skins
- [ ] Undo, tags, stronger search filters and feed preview
- [ ] Configurable hotkey and per-app capture exclusions
- [ ] Windows executable installer and signed release pipeline

## v0.3 — selection catcher

- [ ] Windows UI Automation text-selection adapter: explicit opt-in and visible activity indicator
- [ ] Mac Accessibility + Linux AT-SPI selection adapters
- [ ] Portal entrance near the text-selection bounding rectangle
- [ ] Animated snatch without hidden storage; explicit save or gesture required
- [ ] On/off switch, snooze, allow/deny apps

## v0.4 — second-brain expansion

- [ ] Browser extension / share target for manual saves
- [ ] OCR and document text extraction, with security limits
- [ ] Local semantic indexing and hybrid search
- [ ] Smart tags, bookmarks, timelines and deduplicated knowledge graphs
- [ ] Secure import/restore and user-owned exports

## v1.0 — production quality

- [ ] Encryption at rest and secure key management
- [ ] Cross-platform GUI automated tests, benchmarks and crash recovery
- [ ] Signed installers, trustworthy updates, security audit
- [ ] Plugin SDK, optional local model connectors, optional second-brain sync

### Inspiration

Useful patterns researched from open-source projects: Shimeji, Desktop Goose, vscode-pets, Tauri desktop-pet overlays, and existing PyQt Desktop Pets. References: https://github.com/YijiaDuan/desktop-pet and https://github.com/LGaben/Desktop-Pets . No third-party character sprites or copyright assets are incorporated.
