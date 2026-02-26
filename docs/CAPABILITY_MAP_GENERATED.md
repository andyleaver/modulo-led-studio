# Capability Map (Generated)

Generated from the **code in this repo** (registered effects + target packs), not from README claims.

Generated at: `2026-02-25T01:37:22Z`

## Summary

- Registered (shipped) effects: **87**
- Target packs: **21**
- Preview-only effects: **5**
- Audio-required effects: **10**

## Effect support (registered)

- Supports strip: **73**
- Supports matrix: **77**
- Supports both strip+matrix: **73**

## Export coverage by target

`effects_preview_ok` counts effects that can run in preview given target capabilities (layout + audio).
`effects_export_ok` excludes effects marked `preview_only`.

See:
- `docs/CAPABILITY_MAP_EFFECTS.csv`
- `docs/CAPABILITY_MAP_TARGETS.csv`

## Notes

- HUB75 targets are **matrix-only** (strip support is false), so effects that only support strip will not apply (currently none in the registered set).
- No-audio targets lose the audio-required effects (currently **10**).

## Engine primitives (audited)

These are **engine-level primitives** (not effects) present in code:

- TimeSource v1 (fixed/realtime/wallclock; deterministic stepping)
- LightPipeline v1 (brightness/gamma/tone; centralized post-compose)
- SignalBus + derived signals v1 (entropy/activity/occupancy/motion)
- Spatial v1 (semantics) + SpatialTransform v1 (led/layout/world helpers)
- Resource Snapshot v1 (tick/render timing + heuristic warnings)
- Extensions v1 (custom signals, rule actions, health probes, *systems*)
- SystemScheduler v1 (ordered, safe system ticking + audit snapshot)

Simulation primitives:
- ParticleSystem v1 (emitters + modules)
- ParticleRender v1 (point/particle splatting to LEDs)
- VectorFields v1 (constant/radial/vortex/curl-noise)
- Noise v2 (deterministic noise + curl helpers; canonical)
- Buffers v1 (ScalarBuffer/VectorBuffer) + Advection v1 + BufferRender v1
- InfluenceMaps v1 (deposit + sense + gradient steering)
- Integrators v1 (shared kinematics step + drag + clamp)
- Constraints v1 (bounds + obstacles + tilemask + springs)
- ParticlePairs v1 (spatial-hash proximity/collision counting)
- ForceParticlesCore v1 (lifted from force_particles integration)

Lifted reusable cores:
- BoidsCore v1 (lifted from boids_swarm)
- VortexParticlesCore v1 (lifted from vortex_particles)
- ShaderMath v1 (shared math helpers)
