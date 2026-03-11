# Modulo LED Studio — Capabilities

This is the code-based capabilities list for the current baseline.

## Core position

Modulo is a **behavior-driven LED engine**.

It is not just an effect picker. It supports conventional effect-style use, but its actual codebase includes composition, routing, rules, diagnostics, and export systems that go well beyond a normal LED app.

## Implemented and verified today

### Hardware-truthful rendering
- strip and cells/matrix surface support
- deterministic mapping
- canonical width / height / count handling
- mapping transforms:
  - serpentine
  - rotate
  - flip_x
  - flip_y
  - origin
- preview/export mapping parity tooling
- HUB75-capable target infrastructure in export targets

### Layered composition
Canonical layer controls:
- enabled
- opacity
- blend_mode
- order
- params
- operators
- modulotors
- rules
- variables
- target_kind
- target_ref

Blend modes implemented:
- over
- add
- max
- multiply
- screen
- normal (canonicalized)

Project-level postfx:
- trail_amount
- bleed_amount
- bleed_radius

### Rules and variables
- Rules engine
- deterministic evaluation
- trigger/action support
- variable mutation
- layer parameter mutation
- number and toggle variables
- runtime/project sync helpers

### Signals and audio
- signal bus
- time signals
- audio signals
- derived metrics
- purpose channels
- audio routing
- preview/sim audio path
- MSGEQ7 export support

### Spatial targeting
- masks
- composed masks
- mask cycle detection
- groups
- zones
- target-mask filtering
- layer target_kind / target_ref fields

### Diagnostics and self-validation
- Full Health
- Full Audit
- composition probes
- operator override probe
- time/audio signal probes
- canonical resolver probe
- override priority probe
- persistence probe
- export canonical param probe
- preview↔export semantic parity probe
- resolver inspector
- mapping inspector
- rules parity checks
- project round-trip checks
- effect audit
- parity sweep
- release gate
- soak test

### Export pipeline
- export IR
- export gating
- eligibility matrix
- signal expression mapping
- validated firmware/sketch generation
- target-pack validation
- multi-target export support

### Extension hooks
- custom effects
- custom rule actions
- custom signal providers
- custom systems
- custom CA modules

## Bottom line

Current Modulo is already:
- stable
- test-validated
- diagnostics-rich
- export-capable
- architecturally broader than a typical LED app

The next major job is to make the UI and workflow reflect the engine reality.
