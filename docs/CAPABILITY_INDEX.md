# Capability Index (code-derived)

This file is intentionally **code-first**: each capability points to the source files that implement it.

## Core runtime

### Real-time preview engine
- **Files:** `V53_work/app/preview_engine.py`, `V53_work/app/project_manager.py`, `V53_work/runtime/*`
- **What it does:** Builds a frame from enabled layers, applies blend/opacity, and streams the buffer to the UI preview.
- **Enables:** Multiple independent systems (layers) running at once.
- **Example:** *When a layer is toggled off, the engine should rebuild the composite without that layer.*

### Stateful effects (tick + persistent state)
- **Files:** `V53_work/behaviors/stateful_adapter.py`, plus effects that use it.
- **What it does:** Wraps effects with persistent state and a deterministic tick/render loop.
- **Enables:** Game-like behaviour, physics, memory, interactions.
- **Example:** *When `jump_now` becomes 1, the character state transitions run → jump → run.*

## Behaviour + rules

### Rules V6
- **Files:** `V53_work/runtime/rules_v6.py`
- **What it does:** Evaluates triggers (tick / rising / threshold) and runs actions (set vars, set layer params, toggles).
- **Enables:** “Do X when Y happens” without hard-coding logic inside effects.
- **Example:** *When `vars.number.clock.minute_changed` rises, set layer param `jump_now` to 1.*

## Audio

### Real + simulated audio backends
- **Files:** `V53_work/audio/*`
- **What it does:** Provides a consistent signal surface (`audio.energy`, bands, etc.) for both real input and simulation.
- **Enables:** Audio-reactive behaviour that can be authored/tested without hardware.
- **Example:** *When `audio.energy` crosses a threshold, increase speed or spawn particles.*

## Layout + mapping

### Matrix / strip topologies
- **Files:** `V53_work/models/layout.py`, exporters under `V53_work/export/*`
- **What it does:** Defines layout shape and mapping (matrix dimensions, serpentine, flips, rotation).
- **Enables:** Correct preview + firmware export for real wiring.
- **Example:** *When `matrix_rotate=90`, remap pixels accordingly in preview/export.*

## Diagnostics

### Health checks + audits
- **Files:** `V53_work/runtime/health/*`, `V53_work/runtime/effect_audit/*` (and callers)
- **What it does:** Validates projects, checks zones/masks/groups, probes audio snapshot, audits effects.
- **Enables:** Shipping a complex tool without silent regressions.
- **Example:** *When an effect returns blank frames, it appears in the audit summary.*
