# Modulo LED Studio

Modulo LED Studio is a **behavior-driven LED engine** for addressable LEDs.

It can behave like a familiar effect-picker app, but its real purpose is to remove the artificial ceiling imposed by conventional LED apps and open up full control over addressable LEDs.

This README describes **what is actually implemented in the codebase today**.

## What Modulo is

Modulo is not just a list of effects.

In the current codebase it includes:

- canonical project normalization
- strip and matrix/cells surface handling
- layered composition
- behavior registry and shipped behavior set
- rules, variables, and signal routing
- audio-backed signal support
- masks, groups, zones, and targeting infrastructure
- operators and project-level postfx
- live preview rendering
- target-gated firmware export
- diagnostics, triage, parity probes, and soak tooling
- extension hooks for advanced users

## Product structure

Modulo is intended to support three distinct modes:

1. **Era**
   - historical onboarding through LED capability evolution
   - not a normal working tab
2. **Effect Picker App**
   - a simplified, conventional LED-app workflow
3. **Full Modulo App**
   - the no-ceiling environment with full engine power exposed

## Current code-verified status

Based on the current code and validation runs:

- selftests are green
- release gate covers validation, parity sweep, resolver inspection, golden exports, and soak
- target-pack validation is green
- behavior validation is green
- asset validation is green
- in-app Doors Open diagnostics hold up across repeated runs

Modulo is currently in an **engine-stable** state.

## Current UI reality

The engine is ahead of the UI.

What is true in code today:

- backend capability is strong
- diagnostics are strong
- export is strong
- some UI tabs and controls still need workflow reordering and wiring
- Era still needs to be separated from the main workspace flow
- zones / masks / groups / targeting need clearer first-class workflow exposure

## Summary

Modulo LED Studio is currently:

- a stable LED behavior engine
- not just an effect picker
- diagnostics-rich
- export-capable
- significantly broader than a conventional LED app
- still needs workflow-first UI restructuring

## Release hygiene

- Live runtime names use the canonical schema.
- Older input shapes are normalized at boundaries and are not written back into project state.
- Publishable builds should keep shipped names clean and stable.
