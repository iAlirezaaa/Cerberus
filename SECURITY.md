# Security policy

Cerberus v0.1 is experimental desktop software and has not undergone a formal security audit.

**Please do not use the current unencrypted vault to store passwords, API keys, medical records or other sensitive secrets.** Clipboard capture is off by default and can unintentionally save private data if enabled.

## Reporting

For suspected security vulnerabilities, prefer a **private GitHub security advisory** on this repository if that feature is enabled. Do not publish exploitable security details in a public issue. If private advisory reporting is unavailable, request a private reporting channel from the maintainer without disclosing the exploit in public.

## Development expectations

- No silent keyboard, screen, clipboard or accessibility surveillance.
- Respect explicit user consent, denial and revocation.
- Check and bound any imported file content. Never automatically execute imported files.
- Keep the local storage core usable without remote accounts.
- Include reproductions and regression tests with security fixes.
