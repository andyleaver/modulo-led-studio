from __future__ import annotations

"""Effect Audit (preview-side).

Goal:
  - Provide a deterministic, in-app audit that answers:
      *Does each shipped effect actually render something in preview?*

Why this file exists:
  - The original monolithic implementation lived in a large Qt file.
  - After the 15k LOC split, several UI buttons still referenced the old symbols.
  - This module is the stable import target for the Diagnostics tab.

This audit is intentionally conservative:
  - It only audits *registered* effects (behaviors.auto_load.register_all()).
  - Audio-reactive effects are skipped unless include_audio=True.
  - "OK" means: at least one LED becomes non-black in the probe window.
  - "ANIM" means: the frame hash changes over time.
"""

# --- diagnostics helper (no silent failure) ---
try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None


def _diag_exc(e: Exception, where: str):
    try:
        if _DIAGS is not None:
            _DIAGS.exception(e, domain="PROJECT", code="EFFECT_AUDIT_EXCEPTION", summary=where)
    except Exception:
        pass


from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.app_identity import get_app_id

def _now_iso() -> str:
    try:
        import datetime as _dt
        return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return ""

def _ensure_registry_populated() -> None:
    try:
        from behaviors.registry import REGISTRY
        if isinstance(REGISTRY, dict) and len(REGISTRY) > 0:
            return
    except Exception as e:
        _diag_exc(e, "app/effect_audit.py")
    try:
        from behaviors.auto_load import register_all
        register_all()
    except Exception:
        # If registration fails, caller will report via exception.
        return

def _caps() -> dict:
    try:
        from behaviors.registry import load_capabilities_catalog
        return load_capabilities_catalog() or {}
    except Exception:
        return {}

def _is_audio_effect(key: str) -> bool:
    try:
        eff = (_caps().get("effects") or {}).get(str(key), {}) or {}
        return bool(eff.get("requires_audio", False))
    except Exception:
        return False

def _kernel_has_user_code(project_dict: dict) -> bool:
    """Return True only when the current project actually authors kernel code.

    Kernel is an escape hatch. Blank is expected when no custom preview/export code exists.
    A kernel layer is considered authored when params.py or params.cpp contains non-empty text.
    """
    try:
        layers = (project_dict or {}).get("layers") or []
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            beh = str(layer.get("behavior") or "")
            kind = str(layer.get("kind") or "")
            if beh not in ("kernel", "write_the_loop") and kind != "kernel":
                continue
            params = layer.get("params") or {}
            py = str(params.get("py") or "").strip()
            cpp = str(params.get("cpp") or "").strip()
            if py or cpp:
                return True
    except Exception:
        pass
    return False

def _mk_probe_project(project_dict: dict, effect_key: str) -> Any:
    """Create a minimal Project model for the preview engine."""
    from models.project import Project, Layout, Layer
    from app.project_model import get_surface_spec, build_layout_model

    p = project_dict if isinstance(project_dict, dict) else {}
    spec = get_surface_spec(p)
    if spec is None:
        raise RuntimeError('unable to derive canonical SurfaceSpec for effect audit')
    surface = build_layout_model(p)

    # Use the first layer's params as a base so effects get realistic defaults.
    base_layer = None
    try:
        layers = p.get("layers") or []
        if isinstance(layers, list) and layers:
            if isinstance(layers[0], dict):
                base_layer = layers[0]
    except Exception:
        base_layer = None
    params = {}
    if isinstance(base_layer, dict):
        params = dict(base_layer.get("params") or {})

    layer = Layer(
        uid="audit",
        name=f"audit:{effect_key}",
        behavior=str(effect_key),
        enabled=True,
        opacity=1.0,
        blend_mode="over",
        target_kind="all",
        target_ref=0,
        params=params,
        modulotors=[],
        variables=[],
        rules=[],
        operators=[],
    )
    proj = Project(layers=[layer], ui={'selected_layer': 0}, groups=[], zones=[], rules=[])
    proj.surface = surface
    return proj

def _frame_sig(frame: List[Tuple[int, int, int]]) -> str:
    """Stable digest for a frame."""
    h = hashlib.sha1()
    for r, g, b in frame:
        h.update(bytes((int(r) & 255, int(g) & 255, int(b) & 255)))
    return h.hexdigest()

def _probe_effect(effect_key: str, project_dict: dict, *, include_audio: bool) -> dict:
    from preview.preview_project_bridge import make_preview_engine_from_project_dict
    from preview.audio import AudioSim

    # Build a safe isolated engine so diagnostics doesn't mutate the live UI engine.
    audio = AudioSim()
    proj = _mk_probe_project(project_dict, effect_key)
    eng, _, _ = make_preview_engine_from_project_dict(proj, audio=audio)

    # Step a wider deterministic window so slow pulses / sparse flashes are still audited fairly.
    # The earlier 6-frame (~0.17s) window falsely marked effects like pulse/lightning BLANK.
    lit = 0
    uniq = 0
    sigs = []
    sample_times = [
        0.0, 1.0/30.0, 2.0/30.0, 3.0/30.0, 4.0/30.0, 5.0/30.0,
        0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0
    ]
    for t in sample_times:
        try:
            frame = eng.render_frame(float(t))
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}
        if not isinstance(frame, list):
            return {"status": "ERROR", "error": "render_frame did not return list"}
        # Count lit LEDs
        try:
            lit += sum(1 for (r, g, b) in frame if (int(r) | int(g) | int(b)) != 0)
        except Exception as e:
            _diag_exc(e, "app/effect_audit.py")
        try:
            uniq = max(uniq, len({(int(r), int(g), int(b)) for (r, g, b) in frame}))
        except Exception as e:
            _diag_exc(e, "app/effect_audit.py")
        sigs.append(_frame_sig([(int(r), int(g), int(b)) for (r, g, b) in frame]))

    anim = "YES" if (len(set(sigs)) > 1) else "NO"
    if lit > 0:
        status = "OK"
    elif str(effect_key) == "kernel":
        status = "BLANK" if _kernel_has_user_code(project_dict if isinstance(project_dict, dict) else {}) else "EXPECTED_BLANK"
    else:
        status = "BLANK"
    return {"status": status, "lit": lit, "uniq": uniq, "anim": anim}

def run_effect_audit(project: dict, *, include_audio: bool = False, app_core=None, controller=None) -> dict:
    """Return a machine-readable summary."""
    _ensure_registry_populated()
    from behaviors.registry import list_effect_keys

    keys = list_effect_keys()
    caps = _caps().get("effects", {}) or {}

    summary = {"OK": 0, "EXPECTED_BLANK": 0, "BLANK": 0, "SKIP(audio)": 0, "ERROR": 0}
    non_ok: List[Tuple[str, dict]] = []

    for key in keys:
        if (not include_audio) and _is_audio_effect(key):
            summary["SKIP(audio)"] += 1
            continue
        res = _probe_effect(key, project if isinstance(project, dict) else {}, include_audio=include_audio)
        st = str(res.get("status", "ERROR"))
        if st not in summary:
            summary[st] = 0
        summary[st] += 1
        if st != "OK":
            non_ok.append((key, res))

    return {
        "timestamp": _now_iso(),
        "app_id": get_app_id(Path(__file__)),
        "include_audio": bool(include_audio),
        "effects_total": len(keys),
        "summary": summary,
        "non_ok": [{"behavior": k, **v} for k, v in non_ok],
    }

def run_effect_audit_detail(project: dict, *, include_audio: bool = False, app_core=None, controller=None) -> str:
    """Return a human-readable report."""
    rep = run_effect_audit(project, include_audio=include_audio, app_core=app_core, controller=controller)
    lines = []
    lines.append("=== EFFECT AUDIT REPORT ===")
    lines.append(f"timestamp: {rep.get('timestamp','')}")
    lines.append(f"app_id: {rep.get('app_id','')}")
    lines.append(f"include_audio: {rep.get('include_audio', False)}")
    lines.append("note: kernel is an escape hatch: EXPECTED_BLANK only when no authored kernel code exists; authored kernel that stays black is BLANK, authored kernel that throws is ERROR")
    lines.append("")
    s = rep.get("summary", {}) or {}
    lines.append("== Behavior Audit Summary ==")
    for k in ["OK", "EXPECTED_BLANK", "BLANK", "SKIP(audio)", "ERROR"]:
        if k in s:
            lines.append(f"{k}: {s.get(k)}")
    # any extra keys
    for k, v in s.items():
        if k not in ("OK", "BLANK", "SKIP(audio)", "ERROR"):
            lines.append(f"{k}: {v}")
    lines.append("")

    non_ok = rep.get("non_ok", []) or []
    if non_ok:
        lines.append("non-OK / expected blank:")
        for item in non_ok:
            ek = item.get("behavior")
            st = item.get("status")
            lit = item.get("lit")
            uniq = item.get("uniq")
            anim = item.get("anim")
            err = item.get("error")
            if err:
                lines.append(f"  - {ek} — {st} — {err}")
            else:
                lines.append(f"  - {ek} — {st} — lit {lit}, uniq {uniq}, anim {anim}")
    else:
        lines.append("non-OK: none")

    return "\n".join(lines)
