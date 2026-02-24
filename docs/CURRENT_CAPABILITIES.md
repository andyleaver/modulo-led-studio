# Current Capabilities (Audited)

This file describes **what Modulo LED Studio can do today**, as shipped in this ZIP.

- No roadmap language.
- No "nearly ready" claims.
- Capabilities are described at the **engine / behaviour** level (not as an effect list).

For implementation anchors (exact files/lines), see **CODE_AUDIT_LEDGER.md**.

## 1) Hardware‑truthful rendering
- Strip and matrix layouts.
- Cell-based matrix rendering with deterministic LED index mapping.
- Orientation controls (serpentine, flips, rotations as implemented in the layout/mapping pipeline).
- HUB75 matrix paths are present and exercised by included demos/targets.

## 2) Layered composition (multiple systems at once)
- Multiple layers render every frame.
- Each layer runs independent logic and is composited deterministically.
- Layer toggles are wired and verified by UI action diagnostics.

## 3) Stateful behaviour (memory over time)
- Effects can retain state across frames using the stateful adapter pattern.
- Deterministic tick/update/render loop.

## 4) Rules engine (Rules V6)
- Rules can react to time/signal changes (e.g. edge/threshold/tick patterns supported by the Rules V6 implementation).
- Rules can set variables/toggles and drive supported layer parameters.

## 5) Signal bus (audio + time as first‑class inputs)
- Simulated audio backend (always available).
- Real audio backend integration points exist.
- Audio energy/bands are distributed via the signal bus for rules and behaviours to consume.

## 6) Continuous systems (forces / fields)
- Particle/field dynamics are implemented (attract/repel style behaviour).

## 7) World abstractions
- Tilemaps and scrolling worlds are implemented and demonstrable.

## 8) Sprite/actor systems
- Multi-frame sprite animation.
- Independent sprite layers.

## 9) Diagnostics & self‑validation
- Health check report (validation + probes).
- Effect audit summary.
- Preview render probes (nonzero output checks).
- Codemap locations (file/line anchors).
- Release gate + soak tooling shipped.

## 10) Export pipeline with validation
- Firmware export pipeline is present.
- Export eligibility/validation reports explain blockers clearly.
- ESP32 HUB75 targets include WiFi features in generated firmware where applicable (e.g. OTA update endpoint, AP fallback, NTP time sync, info/status endpoint), and are documented in the shipped docs.

---

### What Modulo is (today)
Modulo treats LEDs as a **behaviour system**:
- stateful,
- layered,
- driven by rules and signals,
- with diagnostics that make correctness visible.

