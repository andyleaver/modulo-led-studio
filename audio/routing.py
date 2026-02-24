from __future__ import annotations
from typing import Dict

# Public list used by the UI (Audio Routing window).
# Keep these in sync with resolve_source().
SOURCES = [
    # Broad bands
    "bass", "mid", "high",
    # Energy
    "energy_mono", "energy_l", "energy_r",
    # Per-band levels (MSGEQ7 style)
    "l0", "l1", "l2", "l3", "l4", "l5", "l6",
    "r0", "r1", "r2", "r3", "r4", "r5", "r6",
    # Simple derived events
    "kick", "snare",
    # Beat/tempo
    "beat", "beat_l", "beat_r",
    "onset", "bpm", "bpm_conf", "sec_change",
]

def clamp01(x: float) -> float:
    try:
        x = float(x)
    except Exception:
        x = 0.0
    if x < 0.0: return 0.0
    if x > 1.0: return 1.0
    return x

def resolve_source(audio_events: Dict[str,float], audio_tempo: Dict[str,float], name: str) -> float:
    ev = audio_events or {}
    tp = audio_tempo or {}
    if name == "bass":
        return clamp01(0.25 * ((ev.get("l0_level",0)+ev.get("l1_level",0)+ev.get("r0_level",0)+ev.get("r1_level",0)) or 0.0))
    if name == "mid":
        return clamp01(((ev.get("l2_level",0)+ev.get("l3_level",0)+ev.get("l4_level",0)+ev.get("r2_level",0)+ev.get("r3_level",0)+ev.get("r4_level",0)) or 0.0)/6.0)
    if name == "high":
        return clamp01(((ev.get("l5_level",0)+ev.get("l6_level",0)+ev.get("r5_level",0)+ev.get("r6_level",0)) or 0.0)/4.0)
    if name in ("energy_l","energy_r","energy_mono"):
        return clamp01(float(ev.get(name,0.0) or 0.0))
    if name.startswith("l") and len(name)==2 and name[1].isdigit():
        return clamp01(float(ev.get(f"l{int(name[1])}_level",0.0) or 0.0))
    if name.startswith("r") and len(name)==2 and name[1].isdigit():
        return clamp01(float(ev.get(f"r{int(name[1])}_level",0.0) or 0.0))
    if name in ("kick","snare"):
        if name=="kick":
            return clamp01(max(float(ev.get("l0_tr",0.0) or 0.0), float(ev.get("r0_tr",0.0) or 0.0)))
        return clamp01(max(float(ev.get("l3_tr",0.0) or 0.0), float(ev.get("r3_tr",0.0) or 0.0)))
    if name == "onset":
        return clamp01(float(tp.get("tempo_onset",0.0) or 0.0))
    if name in ("beat","beat_l","beat_r"):
        return clamp01(float(ev.get(name,0.0) or 0.0))
    if name == "bpm":
        bpm = float(tp.get("tempo_bpm",120.0) or 120.0)
        return clamp01((bpm-60.0)/120.0)
    if name == "bpm_conf":
        return clamp01(float(tp.get("tempo_conf",0.0) or 0.0))
    if name == "sec_change":
        return clamp01(float(tp.get("sec_change",0.0) or 0.0))
    return clamp01(float(ev.get(name,0.0) or 0.0))

def compute_zone_levels(project: dict, audio_events: dict, audio_tempo: dict) -> Dict[str,float]:
    routes = (project or {}).get("audio_routes") or []
    levels: Dict[str,float] = {}
    for r in routes:
        try:
            src = str(r.get("source","energy_mono"))
            tgt = str(r.get("target",""))
            if not tgt:
                continue
            scale = float(r.get("scale",1.0))
            mode = str(r.get("mode","add"))
            v = resolve_source(audio_events, audio_tempo, src) * scale
            if mode == "mul":
                levels[tgt] = clamp01((levels.get(tgt,1.0)) * v)
            else:
                levels[tgt] = clamp01(levels.get(tgt,0.0) + v)
        except Exception:
            continue
    return levels
