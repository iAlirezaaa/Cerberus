# Contributing to Cerberus

Cerberus is an early local-first desktop software prototype. Contributions to capture adapters, security, test coverage, accessibility and animation quality are welcome.

## Development

1. Fork and clone the repository.
2. Use Python 3.11+ and create a virtual environment.
3. Install the GUI extras: python -m pip install -e ".[gui]"
4. Run the CLI: python -m cerberus --help
5. Run core tests: python -m unittest discover -s tests -v
6. Run GUI smoke tests with QT_QPA_PLATFORM=offscreen (Windows CI also runs these).

## Pull requests

Keep changes focused. Add tests for persistence/capture behavior. Explain operating systems affected, UI screenshots if applicable, and how the behavior was tested. Avoid adding telemetry or remote services as implicit dependencies. Keep passwords and personal information out of test fixtures.

## Architecture contract

The storage package must remain GUI-independent. The desktop layer should not write directly to database tables. New capture sources must default to OFF unless explicitly triggered by the user; see docs/PRIVACY.md.

## Art assets

Only submit original art, properly licensed assets with attribution, or assets explicitly owned by the contributor. Do not introduce copyrighted characters from other desktop pet projects.
