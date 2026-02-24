# Modulo LED Studio

Modulo LED Studio is a **behaviour-driven LED authoring tool**: you build **layered systems** with **state**, **rules**, and **signals** (audio/time), rather than selecting preset “effects”.

This repository is **audit-first**: documentation only describes what is implemented and verifiable **today**.

## Start here

- Launch: `./RUN.sh` (or `./run.sh`)
- Open the default demo project and explore by toggling layers and rules.
- Run the release gate: `./RUN_RELEASE_GATE.sh`

## What Modulo can do today (engine capabilities)

These are **engine-level capabilities**, not a marketing list of effects:

- **Hardware-truthful rendering**: strip + matrix layouts, orientation/serpentine handling, deterministic LED mapping (incl. HUB75 paths).
- **Layered composition**: multiple independent layers rendered and composited every frame.
- **Stateful behaviour**: behaviours can keep memory over time (tick → update → render).
- **Rules (Rules V6)**: triggers (tick/edges/thresholds) drive actions (vars/toggles/params where supported).
- **Signals**: shared signal bus, with **audio** (sim + real backend) and **time/clock** inputs usable by behaviours and rules.
- **Continuous systems**: forces/fields (e.g. attract/repel) and particle-style dynamics.
- **World abstractions**: tilemaps and scrolling worlds decoupled from sprite/actor logic.
- **Diagnostics**: health checks, audits, preview render probes, and a codemap pointing to exact source locations.
- **Export pipeline**: firmware export with validation and clear blockers; ESP32 HUB75 targets include WiFi features like web update (OTA), AP fallback, NTP sync, and an `/info` endpoint (where supported by target).

See **CURRENT_CAPABILITIES.md** for the audited capability list in a single page (also at `docs/CURRENT_CAPABILITIES.md`).

## Audit ledger (source of truth)

If you want to know **exactly where** each capability lives in the code (file + line anchors) and which shipped demos prove it:

- `CODE_AUDIT_LEDGER.md` (also mirrored at `docs/CODE_AUDIT_LEDGER.md`)

Contributors: use the **codemap** in the in-app Health report and the audit ledger above to avoid “hunt the codebase”.

## Notes on positioning

Modulo is intentionally **not** an effect picker. It’s a behaviour engine for addressable LEDs: things can happen **when something happens** (time, audio, state, rules), with multiple systems running together.

