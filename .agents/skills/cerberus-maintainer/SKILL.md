---
name: cerberus-maintainer
description: Develop, review, package, or document the Cerberus desktop companion in this repository while preserving its local-first capture contract, Qt/core boundary, animation asset rules, and Apache-2.0 licensing.
---

# Cerberus maintainer

Use this skill for changes to the Cerberus desktop pet, capture vault, archive UI, animation assets, packaging, or project documentation.

## Before changing code

- Read `AGENTS.md`, `docs/AGENT_HANDOFF.md`, `docs/ARCHITECTURE.md`, `docs/PRIVACY.md`, `docs/ROADMAP.md`, `LICENSE`, and `NOTICE`; inspect the current branch, worktree, relevant tests, open issues, and CI before selecting work.
- Preserve unrelated user changes and use an isolated test data directory (`CERBERUS_HOME`). Follow the repository's own validation commands and report exactly which environments ran.
- Match claims to evidence. Qt offscreen checks do not prove real Windows drag/drop, click-through, DPI, multi-monitor, sleep/resume, or performance behavior.

## Product and architecture invariants

- Keep the vault local-first. Do not add sign-in, telemetry, remote upload, cloud dependencies, or required API keys.
- Capture only through an explicit user action or a clearly consented opt-in feature. Clipboard collection stays OFF by default; selecting text alone must never save it.
- Keep persistence and input validation in `cerberus/vault.py`; it must remain independent of Qt. Preserve bounded reads, deduplication, content-addressed copies, and the invariant that source files are never moved, executed, or deleted.
- Use `cerberus/motion.py` as the animation state source of truth. Respect reduced motion, keep idle work light, and preload bounded local frames before painting.
- Preserve transparent backgrounds and the three-head character identity. `cerberus/assets/guardian.svg` is a fallback; the raster pack format and resource limits are described in `docs/ANIMATION_PACK.md`. Do not describe single-pose whole-image transforms as a skeletal rig or authored full sprite cycle.
- Do not claim UI Automation selection capture, encrypted storage, OCR, semantic search, native pixel click-through, or real-device validation unless implemented and verified.

## Licensing and assets

- This repository revision is offered under Apache-2.0. Preserve `LICENSE`, `NOTICE`, third-party notices, and asset provenance in source and packaged distributions.
- Older releases may carry MIT or the former Cerberus Personal & Paid Production License. Their existing grants remain; the current Apache-2.0 grant applies only to materials the relevant rights holders can license.
- The Apache license does not grant trademark rights to represent a fork as official. Do not import unlicensed character art, fonts, code, or other third-party assets.
- Do not change the project license again unless the repository owner explicitly directs it. No CLA, copyright assignment, paywall, or licensing service is currently part of the project.

## Finishing a change

Add focused regression coverage and update the README, changelog, architecture, privacy notes, roadmap, or packaging metadata when the change affects them. For GUI changes, run the offscreen smoke suite and render/inspect a preview where the environment permits. Keep the final report explicit about test results, CI state, commit/PR, and unverified native behavior.
