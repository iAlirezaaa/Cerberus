# Design: vault previews, vault location, minimized mode, item icons, Codex art

Status: draft for review · Scope: one feature branch · Platform focus: Windows 10/11

## 1. Problem

1. The memory vault window shows almost nothing about a saved item: text is shown, images get a
   thumbnail, every other file says "FILE ATTACHMENT · OPEN MANUALLY".
2. Where memories are stored can only be seen and changed inside the Settings window, not in the
   vault window where people look for their data.
3. Getting Cerberus out of the way is clumsy: the options are hiding it from the tray, or sending it
   away so it runs off-screen. There is no quick "make it small but keep it handy" mode.
4. Items given to Cerberus have no designed icons. The carry animation uses the Windows file icon.
5. Several animation clips do not connect (for example asleep → sitting jumps; walking reuses the run
   clip at low speed). Codex is generating the missing clips and icons into `art/codex/`.

## 2. Goals and non-goals

Goals:

- A preview for every common item type, without running or opening anything outside the app.
- Storage location visible in the vault window and changeable there, with the same copy-don't-move
  rule as Settings.
- A one-click minimized mode that keeps Cerberus as a small bubble that still accepts drops.
- Designed per-kind icons in the carry animation, the vault list and the preview.
- Wire Codex clips into the state machine when they pass quality checks; ignore the rest.

Non-goals: audio/video playback inside the app, editing items, syncing, OCR.

## 3. Item kinds (new Qt-free module `cerberus/item_kinds.py`)

A pure function maps a vault item to a kind: `text`, `link`, `image`, `pdf`, `document`,
`spreadsheet`, `presentation`, `archive`, `code`, `audio`, `video`, `app`, `font`, `email`,
`model3d` or `file`. It uses the item's `kind` column (text/url/file) and the original file
extension. It also says how to preview it: `text`, `image`, `animated_image`, `pdf`, `text_file`
or `icon_only`.

## 4. Vault preview

Shown in the right-hand card when an item is selected. All file previews read only files inside
the vault's own `files/` folder (current rule), never the original location.

| preview | how | limits |
| --- | --- | --- |
| text / link | full text, read-only, selectable; links get an "Open link" button | 20 000 characters shown |
| image | `QImageReader` scaled to the card | refuse > 40 MP |
| animated GIF / WebP | `QMovie` scaled to the card, stops when the selection changes | refuse > 40 MP per frame |
| pdf | `QPdfDocument` renders page 1 to an image, shows page count | file already ≤ 50 MiB |
| text file (.txt .md .json .csv .py .js .log …) | first 64 KiB decoded as UTF-8 (errors replaced), monospace | 64 KiB |
| anything else | the kind's animated icon, file type, size, original name | — |

Rendering is synchronous on selection. Expected cost: PDF page 1 in under ~200 ms for normal
documents. The vault list shows a 32 px kind icon next to each row.

## 5. Vault location in the vault window

A strip under the title: `Stored in: <folder>` plus **Open folder** and **Change…**. Change uses
the same controller method as Settings (`Controller.change_storage`): if the target already has a
vault, ask to switch to it; otherwise ask whether to copy current memories (originals are never
deleted). The dialog logic moves from `SettingsWindow` into a shared helper so both windows behave
the same.

## 6. Minimized mode

- Entry points: a **–** hover button on Cerberus (next to the existing ↗ send-away button), a tray
  menu item "Minimize / restore", a single click on the tray icon, and a new shortcut action
  "minimize / restore".
- Effect: the pet window hides immediately (plays `portal_exit` first when that clip exists) and a
  96 px bubble appears where Cerberus's feet were. The bubble animates `mini_curl` when available,
  otherwise a still image of the heads, at about 8 fps.
- The bubble: click restores Cerberus at the same place (portal entrance); left-drag moves it;
  dropping text, links, images or files on it captures them **without restoring** (the bubble
  flashes and shows a short tooltip); right-click opens the tray menu.
- While minimized: the pet's timer is stopped, no roaming, chat, sleeping or wandering off.
- Persisted: `settings.minimized` and the bubble position, so a restart keeps the bubble.
- The existing "away" dock (after wandering off) remains a separate state, placed at the screen
  edge. Both use the same bubble widget class with different placement.

## 7. Designed item icons

Codex delivers `icons/<kind>.png` (128 px) and `icons/<kind>.gif`. Accepted icons are copied to
`cerberus/assets/icons/`. Use: carry animation (static PNG, drawn on the scroll), vault list
(PNG at 32 px), preview card for `icon_only` items (GIF). Missing icons fall back to the
system file icon, then to the drawn glyphs that exist today.

## 8. Codex clips

Accepted clips are copied to `cerberus/assets/clips/<name>/NN.png` (RGBA PNG keeps soft glow
edges, unlike GIF). The manifest gains `"anchored": true` for PNG lists so they are cropped and
stand on the ground line like GIFs. Planned wiring:

| clip | used when |
| --- | --- |
| `wake_up` | sleep → idle (replaces reversed fall-asleep) and before running off |
| `sit_to_run`, `run_to_sit` | start and end of a stroll or run |
| `turn_around` | facing direction changes while sitting |
| `walk` | strolls (replaces slow-motion run) |
| `held` | while being dragged |
| `petted` | click / petting (alternates with play) |
| `sad` | capture error |
| `portal_exit` | send away and minimize |
| `stash_item` | end of capture (replaces data snack) |
| `talk`, `think` | while a speech / thought bubble is showing |
| `sniff` | something dragged over Cerberus |
| `yawn`, `scratch_ear`, `chase_tail`, `heads_argue` | extra idle variants |
| `howl` | idle variant only between 20:00 and 05:00 |
| `peek_in` | coming back from the edge dock |
| `mini_curl`, `mini_wake` | minimized bubble idle / hover |

Acceptance gate per clip: manifest status `done`, transparent corners, frames share one canvas,
feet within ±6 px of the baseline across frames. Clips failing the gate are listed for the user,
not wired.

## 9. Review response (goldfish review, applied)

| finding | resolution |
| --- | --- |
| Capture while minimized always summoned the pet | `capture()` stores, then `celebrate()`: the bubble flashes when minimized; errors go to a tray notice instead of a dialog |
| Loader rejected new clip names / budgets too small | `ALLOWED_STATES` lists every optional clip; frame limit 400; pixel budget counts cropped pixels (64 MP) |
| Phase durations hard-coded | `MotionMachine.durations` per instance; set from each loaded clip's real length |
| Previews lock files on Windows | images, movies and PDFs decode from a `QBuffer` copy; `Vault.delete` removes the file before the row |
| Rich-text injection, format sniffing, unbounded animations | plain-text labels; magic-byte sniffing with a decoder whitelist; frame and pixel caps; allocation limit; bidi/control characters stripped |
| Synchronous decoding while arrowing through the list | 120 ms debounce; decoding still runs on the GUI thread (known limitation) |
| Four presence states without a matrix | table below, covered by GUI tests |
| Tray single vs double click | single click toggles minimize; double-click no longer has its own action |
| Restore made the pet leave at once | restore uses the active `arrive` transition (tested) |
| Bubble CPU | still image unless hovered, drop-hovered or flashing; never animates with reduced motion |
| Opening runnable files | programs and scripts are never opened; their folder is shown instead |

| state | minimize | restore / summon | send away | capture |
| --- | --- | --- | --- | --- |
| visible | portal exit → bubble at its feet | summon: to the cursor | runs off-screen | pet celebrates |
| away (docked) | dock → bubble | portal at the cursor | — | pet comes back |
| hidden | bubble at the saved spot | shown at the cursor | — | pet comes back |
| minimized | restore | at the bubble / at the cursor | ignored | bubble flashes |

## 10. Risks and open questions

- Generated frames may drift in identity or scale between frames; the gate catches size/baseline,
  not identity. A human look is still needed.
- Memory: each 320 × 640 RGBA clip of 8 frames is ~6.5 MB decoded before cropping. 25 more clips
  could add ~100 MB. Cropping to the visible box roughly halves this; the existing 32 MP pack
  budget must be raised or clips loaded lazily.
- PDF rendering depends on the PySide6 QtPdf module being bundled by PyInstaller.
- Minimized bubble + away dock + pet are three top-level windows; focus and always-on-top
  behaviour must not steal focus from the user's app.
