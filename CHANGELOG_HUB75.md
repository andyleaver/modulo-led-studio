n## V83 (2026-02-24)
- UI Export Diagnostics now include SKIP bucket (target capability limitations) and no longer crash on parity summary.


## HUB75_UI_V75_EXPORT_GAMES_BREAKOUT_ASTEROIDS_PHASE3D__20260224_1900Z
- Phase 3D: Wired Breakout/Asteroids lite runtime into layerstack exporter (behavior ids 9/10) and mapped breakout_game/asteroids_game to those behaviors.
## V71 (Phase 2B)
- Tilemap/Sprite export: per-effect variants (tilemap_sprite / red_hat_runner / mariobros_clockface) encoded via purpose_i0 (PI0).
- purpose_f0: jump trigger (rules settable). purpose_f1: jump height / clock digit scale.

# HUB75 Changelog (local workline)

This file tracks the local HUB75 workline packaging builds.

- V13: HUB75 UI start + tile assets
- V14: HUB75 Tilemap Runner demo
- V15: 2x2 panel demo + jump tick
- V16–V21: mapping presets, clock signals, rules integration, auto chain, panel order presets
- V22–V31: WiFi web update, /info, mDNS, reconnect, AP fallback portal, NTP, hardware validation + mapping diagnostics demos

(Use Git tags/releases for authoritative history once pushed.)


## V77 (2026-02-24)
- Phase 4: Added tools/parity_sweep.py to generate per-target export gating report (CSV+MD).
- Cleaned export eligibility reasons: removed outdated 'Degraded export fallback' text for exportable behaviors.
