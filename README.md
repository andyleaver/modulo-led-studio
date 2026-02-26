# Modulo LED Studio

Modulo LED Studio is a behavior-driven LED authoring engine with real-time preview
and real firmware export.

It is designed to move addressable LEDs beyond simple preset effects and into
layered, stateful, rule-driven systems, while remaining usable by non-coders
and extensible by coders.

This README documents audited, implemented capabilities only.


## What makes Modulo different

Most LED software stops at:
- choosing an effect
- adjusting speed and colour
- looping presets

Modulo treats LEDs as a runtime system.

- Multiple behaviors can run at once
- Behaviors have state and memory
- Rules react to time, audio, and signals
- Output is composited through layers
- Projects export to real firmware


## Core capabilities (current)


### Physical layout and mapping

Modulo supports both 1D LED strips and 2D LED matrices.

LED index mapping is accurate and configurable:
- serpentine wiring on or off
- X and Y flipping
- rotation at 0, 90, 180, or 270 degrees

Preview and export use the same layout model.


### Layered composition

Projects are built from an unlimited layer stack.

Each layer supports:
- enable / disable
- opacity
- blend modes: over, add, max, multiply, screen
- targeting: all LEDs, a zone, or a group

Layer compositing is deterministic.


### Zones and groups

Zones are defined as index ranges.

Groups are arbitrary LED index selections.

Layers may target:
- all LEDs
- a zone
- a group


## Behavior system (not just effects)

Modulo ships with 100 built-in behaviors.

- 92 behaviors are exportable
- 8 behaviors are preview-only (onboarding / era content)

Behaviors are stateful systems, not stateless shaders.

This includes:
- cellular automata
- particle systems
- games and simulations
- clocks and dashboards
- audio-reactive systems

Behaviors persist state across frames and run inside a deterministic update loop.


## Rules engine (automation and logic)

Rules V6 allow logic without writing code.

### Rule triggers
- tick
- threshold (with hysteresis)
- rising edge

### Rule inputs (signal bus)
- time (t, dt)
- engine frame counter
- audio energy
- 7-band mono audio
- 7-band left audio
- 7-band right audio
- user-defined numeric variables
- user-defined toggles

### Rule actions
- set numeric variables
- add to numeric variables
- flip toggles
- adjust export-safe layer parameters
- adjust export-safe operator parameters

Rules are deterministic and exportable.


## Modulation system

Each layer includes modulators that can drive parameters using:
- LFOs
- audio energy
- audio frequency bands

Modulation targets include:
- brightness
- speed
- width
- softness
- density
- purpose-specific channels


## Operators and post-processing

### Operators (per-layer)
- gain
- gamma
- posterize

### PostFX (project-level)
- trail
- bleed (radius-limited)

Post effects are available for both strip and matrix layouts
with export safety checks for memory-limited targets.


## Audio reactivity

Modulo includes a built-in audio signal bus.

- MSGEQ7-style 7-band audio support where hardware allows
- Audio can drive behaviors, modulators, and rules
- Audio support depends on the export target


## Firmware export

Modulo generates real firmware, not configuration files.

The export system includes:
- target-pack architecture
- explicit export eligibility matrix
- clear reports explaining blocked exports

Supported targets in this version include:
- Arduino (FastLED)
- ESP8266
- ESP32 (FastLED with audio support)
- RP2040
- STM32
- Teensy 4.x
- ESP32 HUB75 matrix targets using I2S-DMA

Feature availability depends on target capabilities.


## Coder escape hatches

Modulo is primarily a no-code system, but coder extensions exist.


### Kernel DSL (exportable)

- Shader-like per-pixel expression language
- Sandboxed and validated
- Compiled to C++ at export time
- Fully exportable

This allows coders to write custom pixel logic safely.


### Write the Loop (advanced / hidden)

- Full per-pixel function escape hatch
- Python code used for preview
- C++ code used for export
- Present in the codebase but not enabled by default
- Intended for advanced users who want full control


### Mods and extensions

- Python-based mod and plugin system
- Extend:
  - behaviors
  - rules
  - signal sources
  - diagnostics
- Requires editing files, not in-app scripting

Modulo does not expose a general in-app code editor.
Code access is deliberate and controlled.


## What Modulo is not

- Not a preset effect picker
- Not a timeline sequencer
- Not a live-coding playground
- Not a WLED replacement

Modulo is an authoring engine.


## Status

This project is experimental but functional.

Everything documented here is implemented in this version of the codebase.
No roadmap features are described.


## Philosophy

Addressable LEDs gained enormous power.

Most software never moved past:
“they change colour”.

Modulo exists to move that ceiling.
