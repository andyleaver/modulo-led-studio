# Modulo LED Studio — Code Audit Ledger (V61)

Build audited: `Modulo_LED_Studio__HUB75_UI_V61_GUARDRAILS__20260224_2215Z`  
Audit scope: **Only what is implemented and runnable today in this ZIP.** No roadmap, no “nearly ready”.

This ledger answers two questions:
1) **What can the app do today?** (engine capabilities, not “effect picker” features)  
2) **Where is each capability implemented in code?** (file + line anchors)

---

## A. Core engine capabilities (implemented today)

### 1) Hardware-truthful layout + mapping (strip + matrix + HUB75-aware)
**What you can do:** Author projects against a physical layout (strip or matrix) with deterministic LED index mapping (orientation/serpentine/flip).  
**Where in code:**
- Preview engine consumes layout: `preview/preview_engine.py:923-2026`
- Bridge rebuilds engine from project: `qt/core_bridge.py:97-836`
- Demo loader (featured demos): `app/demo_loader.py:5-13`
**Proof in ZIP:**
- Demo: `demos/demo_hub75_hw_mapping_diagnostics.json` (featured)
- Health report: **PREVIEW RENDER PROBES** must show nonzero for live frames and zero for “all off”.

### 2) Layered composition (multiple concurrent systems)
**What you can do:** Run multiple independent systems simultaneously by stacking layers (each layer ticks independently, then composited).  
**Where in code:**
- Rendering + compositing loop: `preview/preview_engine.py:923-2026`
- Project model ↔ engine model sync: `qt/core_bridge.py:97-836`
**Proof in ZIP:**
- Showcases are explicitly multi-system scenes (see Section C): `app/showcases/registry.py`
- Health report includes layer toggling diagnostics (`UI_TOGGLE_OPERATOR_PERSISTS`, render probes).

### 3) Stateful behaviour (memory over time)
**What you can do:** Effects keep state across frames (counters, positions, modes, simulation state).  
**Where in code:**
- Demonstrated by stateful demos (see Red Hat + game showcases) and preview tick loop: `preview/preview_engine.py:923-2026`
- Example stateful implementation: `behaviors/effects/red_hat_runner.py:58-178`
**Proof in ZIP:**
- Showcase: `Red Hat Runner` (state + rules)
- Showcases `Breakout + Invaders`, `Life + Snake`, `Brain + Life + Ant` are multi-step simulations.

### 4) Rules engine (Rules V6): “when X happens, do Y”
**What you can do:** Author rule-driven behaviour using triggers (time/signal edges/thresholds) and actions (set/add variables, toggles, supported layer params).  
**Where in code:**
- Rules evaluation: `runtime/rules_v6.py:148-539`
- Rules schema/bootstrap: `runtime/rules_v6.py:83-90`
**Proof in ZIP:**
- Featured demo: `demos/demo_red_hat_runner_rules_v6.json`
- Featured demo: `demos/demo_hub75_tilemap_runner_rules_v6.json`

### 5) Signal bus + audio (sim + real backend)
**What you can do:** Use a shared signal bus; simulated audio always works; real audio backend supported when available.  
**Where in code:**
- Signal routing: `runtime/signal_bus.py:43-179`
- Audio service: `runtime/audio_service.py:11-86`
- Preview audio input: `preview/audio_input.py:22-231`
**Proof in ZIP:**
- Health report section **AUDIO DIAGNOSTICS** (shows sim backend + band values).
- Rules can reference signals (`signals: audio.*` appears in report even if not consumed).

### 6) Continuous systems (forces / fields)
**What you can do:** Particle/field behaviour including attract/repel dynamics (continuous positions/velocities).  
**Where in code:**
- Force particles preview implementation: `behaviors/effects/force_particles.py:2305-2371`
**Proof in ZIP:**
- Available as an effect implementation in `behaviors/effects/force_particles.py` (used by showcases/demos if enabled).

### 7) World abstractions (tilemaps + scrolling)
**What you can do:** Render tilemaps and scroll worlds independently of sprite layers.  
**Where in code:**
- Tilemap sprite preview implementation: `behaviors/effects/tilemap_sprite.py:170-368`
**Proof in ZIP:**
- Featured demo: `demos/demo_hub75_tilemap_runner.json`
- Featured demo: `demos/demo_hub75_tilemap_runner_2x2.json`

### 8) Sprite systems (actors, not just frames)
**What you can do:** Independent sprite animation and actor-like state machines (movement, jumping).  
**Where in code:**
- Red Hat runner: `behaviors/effects/red_hat_runner.py:58-178`
**Proof in ZIP:**
- Showcase: `Red Hat Runner`
- Demo: `demos/demo_red_hat_runner_rules_v6.json`

### 9) Diagnostics + self-validation (anti-mystery-failure)
**What you can do:** Get deterministic health reports, effect audits, preview render probes, and codemap anchors (file+line) for key subsystems.  
**Where in code:**
- Health / diagnostics runner: `app/project_diagnostics.py:47-200`
- Codemap generation: `app/codemap.py` (enforced by V61 guardrails)
**Proof in ZIP:**
- Your V61 report shows:
  - Effect Audit Summary OK/BLANK
  - Preview render probes A/B/C/D
  - Codemap entries resolving (including registries)

### 10) Export pipeline with validation + ESP32 HUB75 targets
**What you can do:** Generate firmware projects; get explicit export blockers when something isn’t exportable.  
**Where in code:**
- Export validation + generation: `export/arduino_exporter.py:3058-3234`
- Export eligibility gate: `export/export_eligibility.py:115-119`
- ESP32 HUB75 emitters:
  - `export/targets/esp32_hub75_matrix_noneaudio/emitter.py:11-146`
  - `export/targets/esp32_hub75_i2sdma_noneaudio/emitter.py:19-99`
  - `export/targets/esp32_hub75_i2sdma_grid_noneaudio/emitter.py:19-159`
**Proof in ZIP:**
- Health report **Export Diagnostics** shows correct blocking reason for preview-only behaviours.
- OTA/WiFi/NTP scaffolding is included in emitted firmware strings in `export/arduino_exporter.py` (search `/info` and `/update`).

---

## B. “Where do I edit?” (safe extension points)

- Add/modify behaviours (preview): `behaviors/effects/*.py`
- Register behaviours: `behaviors/registry.py:61-72`
- Showcases (complex composed demos): `app/showcases/*.py` and `app/showcases/registry.py`
- Demo fixtures (JSON projects): `demos/*.json`
- Export targets: `export/targets/*/emitter.py`

Guardrail files:
- Release gate: `RUN_RELEASE_GATE.sh`
- Selftests: `selftest/run_all.py`
- Soak test: `tools/soak_run.py`

---

## C. Built-in showcases (what each proves)
Source: `app/showcases/registry.py`

- **Life + Snake** (`life_snake`) — Two evolving systems layered together
- **Brain + Life + Ant** (`brain_life_ant`) — Three independent systems sharing one space (24×24)
- **Breakout + Invaders** (`breakout_invaders`) — Only after bricks clear: the ball can destroy invaders
- **Red Hat Runner** (`red_hat_runner`) — State + rules: jump on events

---

## D. Featured demo fixtures (what each proves)
Source: `demos/demo_projects.json` (featured=true)

- **Red Hat Runner (Rules)** → `demos/demo_red_hat_runner_rules_v6.json` (state + Rules V6)
- **HUB75 Tilemap Runner (Rules)** → `demos/demo_hub75_tilemap_runner_rules_v6.json` (tilemap + Rules V6)
- **HUB75 Tilemap Runner** → `demos/demo_hub75_tilemap_runner.json` (tilemap scrolling baseline)
- **HUB75 Mapping Diagnostics** → `demos/demo_hub75_hw_mapping_diagnostics.json` (hardware mapping sanity)

Other demos present:
- `demos/demo_hub75_hw_mapping_diagnostics.json`
- `demos/demo_hub75_hw_validation_clockdot.json`
- `demos/demo_hub75_tilemap_runner.json`
- `demos/demo_hub75_tilemap_runner_2x2.json`
- `demos/demo_hub75_tilemap_runner_clock.json`
- `demos/demo_hub75_tilemap_runner_rules_v6.json`
- `demos/demo_hub75_wifi_ntp_clockdot.json`
- `demos/demo_hub75_wifi_ntp_sanity.json`
- `demos/demo_red_hat_runner_rules_v6.json`

---

## E. Audit notes (strict truth)
- This ledger intentionally describes **capabilities** (layers, rules, signals, state, export validation), not a list of “effects”.
- Export diagnostics in V61 correctly state that `red_hat_runner` is **preview-only** (so contributors don’t chase the wrong export error).
