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


## Licensing of contributions

Current Cerberus revisions use the project-specific [Personal & Paid Production License](LICENSE), not MIT or an OSI-approved open-source license. Do not submit third-party code or assets you lack rights to license. When contributing, explain any imported code, its copyright owners and exact license. A pull request must not imply the project can relicense code it does not control. Historical MIT grants remain in place; see [Licensing](docs/LICENSING.md). If a change affects commercial terms, obtain maintainer approval before merging.
