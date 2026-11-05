# Privacy and security

Cerberus is a user-controlled information catcher, not a surveillance app.

### Today

- Capture occurs from deliberate drag/drop, manual CLI, manual clipboard feed, or separately **opted-in** clipboard monitoring.
- Clipboard monitoring is OFF by default.
- Merely selecting or highlighting text in another application does NOT capture it.
- No remote API calls, cloud accounts, analytics, tracking or automatic network uploads are required.
- SQLite and copied attachments are kept on the user's machine, under the OS user-data folder, unless CERBERUS_HOME points elsewhere.
- Source files are copied, never moved or deleted.
- Files are limited to 50 MiB, text to 1 MiB. Current exported JSON includes text and metadata, not file contents.
- The vault is NOT encrypted at rest; do not store passwords, tokens or other secrets.
- Summon shortcuts (Windows): the chosen mouse gesture uses a low-level mouse hook that looks only at which button was pressed or released, and swallows just the presses that form the gesture. The keyboard shortcut uses RegisterHotKey, which never sees other keys. Nothing is logged or stored. Both can be turned off in Settings.
- Vault previews decode an in-memory copy of the stored file (images, PDF page 1, the first 64 KB of text). Nothing is uploaded, and programs/scripts are never opened or run from the vault.
- When "walk around" is on, the pet reads the current cursor position about once a second only to decide which way to face. It is not stored.

### Important clipboard warning

When the optional clipboard watcher is ON it can capture newly copied private text from any application. Do not enable it when copying passwords, bank details or confidential records. A robust app-level exclusion list and warning surface must precede general distribution.

### Deletion

Deleting a file entry removes the imported copy only if it is in the Cerberus file store. It never removes the original. SQLite deletion does not guarantee secure erasure from physical disks, backups or snapshots.

### Later

Accessibility-based selection detection, OCR, semantic analysis, sync and browser integrations must be separate opt-in capabilities with understandable permission prompts, pause buttons and data provenance.
