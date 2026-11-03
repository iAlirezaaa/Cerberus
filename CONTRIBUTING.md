# Contributing to Cerberus

Thanks for helping improve Cerberus. By submitting a pull request, you offer your contribution under the repository's Apache License 2.0, unless you clearly identify a separately licensed component and its terms before submission. You retain copyright in your contribution; no copyright assignment or CLA is currently required.

Cerberus is an early local-first desktop software prototype. Contributions to capture adapters, security, test coverage, accessibility, retrieval, and animation quality are welcome.

Only submit code, art, fonts, and documentation that you have the right to contribute. Include the source and license for third-party material and keep its notices intact. Mark modified files and preserve copyright and attribution notices as required by Apache-2.0. Do not imply that a fork is an official Cerberus release.

## Development checks

Use Python 3.11 or newer and follow the setup in the [README](README.md). Before requesting review, run:

```powershell
python -m compileall -q cerberus tests scripts
python -m unittest discover -s tests -v
```

For GUI changes, run the Qt smoke tests with `QT_QPA_PLATFORM=offscreen` and render the preview with `python scripts/render_preview.py` when the GUI dependencies and Pillow are installed. An offscreen pass does not prove native Windows desktop behavior; include OS and reproduction details for platform-specific changes.

Keep capture explicit, local-first, and privacy-preserving. See [AGENTS.md](AGENTS.md), [Privacy](docs/PRIVACY.md), and the [Cerberus maintainer skill](.agents/skills/cerberus-maintainer/SKILL.md) for project-specific invariants.

## Pull requests and architecture

Keep changes focused. Add tests for persistence and capture behavior. Explain affected operating systems and test evidence; include screenshots for visible UI changes when practical. Keep passwords and personal information out of fixtures.

The storage package must remain independent of Qt. The desktop layer uses the Vault API and must not write directly to database tables. New capture sources must be explicit or default OFF; see [Privacy](docs/PRIVACY.md).

## Art assets

Submit original art or material you have permission to redistribute. Include its source and license, preserve attribution, and do not add copyrighted characters from other desktop-pet projects without authorization.
