# Modulo LED Studio (Experimental)

**Modulo LED Studio** is an **experimental LED authoring tool** designed to move beyond simple
“effect pickers” and toward **building, understanding, and evolving LED behaviour systems**.

This project is intentionally early-stage and community-facing.  
It is not a finished consumer product — it is a foundation.

---

## What Modulo Is

Modulo is a **behavior-driven LED system designer**.

Instead of choosing from fixed presets, users can:
- Build LED behaviour layers
- Combine effects, rules, and signals
- Preview everything live
- Export real Arduino `.ino` code (where supported)

The goal is not just visuals, but **understanding how LED systems work**.

---

## What Modulo Is *Not*

- ❌ Not a polished end-user LED controller
- ❌ Not a preset/effect pack
- ❌ Not guaranteed stable or complete
- ❌ Not locked to Arduino only (export paths are evolving)

This release is **experimental by design**.

---

## Current Capabilities

- Strip and matrix layouts
- Live preview engine
- Layered effects (e.g. Sparkle, Rainbow, Chase, etc.)
- Stateful showcase behaviours (e.g. grid/maze systems)
- Audio simulation backend (no hardware required)
- Diagnostics and health reporting
- Fail-loud export validation (no silent broken exports)

Some behaviours are **layout-specific** (e.g. matrix-only) and will be marked as such.

---

## Preview vs Export Truth

A core rule of Modulo:

> **If something can be previewed, it must be explicitly marked whether it can be exported.**

- Unsupported exports are blocked with clear reasons
- Experimental behaviours may be preview-only
- No “magic” features that silently disappear on hardware

---
## Quick Start

### Requirements
- Python 3.10+
- Qt (via PySide / PyQt as bundled)

### Run
```bash
python3 modulo_designer.py --qt
