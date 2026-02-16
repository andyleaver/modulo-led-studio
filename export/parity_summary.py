from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from export.targets.capabilities import normalize_capabilities
from export.targets.registry import list_targets, resolve_requested_backends
from export.export_eligibility import get_eligibility, ExportStatus

# Effects that are intentionally preview-only utilities.
# They may be enabled for preview/diagnostics, but are ignored by Arduino export.
NON_EXPORT_LAYER_EFFECTS = {"audio_meter"}



# --- UI/Diagnostics Adapter Layer ---
#
# The Qt UI and the Health Check report intentionally consume a dict-based
# "parity summary" with per-layer export eligibility.
#
# Historically this module returned a ParitySummary dataclass only. That made
# parity invisible in the report/UI (silently treated as "not available").
#
# REFAC37 adds a small adapter surface:
#   - build_parity_summary(project, target_id=...)
#   - summarize_layers(project, target_id=...)
#   - layer_parity(...), layer_tag_text(...)
#   - format_project_badge(...), format_export_report_line(...),
#     format_export_block_message(...)
#
# These functions are intentionally best-effort and fail-safe: they never
# throw, and they always return a usable dict/string.


@dataclass
class ParitySummary:
    ok: bool
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "suggestions": list(self.suggestions),
        }


# Minimal export-eligible behavior set (fail-closed).
ELIGIBLE_BEHAVIORS = {
    "solid",
    "chase",
    "wipe",
    "sparkle",
    "scanner",
    "fade",
    "strobe",
    "rainbow",
    "bouncer",
}


def _as_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None


def _norm_pin(v: Any) -> Optional[str]:
    """Normalize a pin representation for comparisons.
    - ints -> "6"
    - strings -> uppercase trimmed ("A0")
    """
    if v is None:
        return None
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        s = v.strip()
        return s.upper() if s else None
    return None


def compute_export_parity_summary(project: Dict[str, Any], target_meta: Dict[str, Any]) -> ParitySummary:
    errors: List[str] = []
    warnings: List[str] = []
    suggestions: List[str] = []

    project = project or {}
    export_cfg = project.get("export") or {}
    layout = project.get("layout") or {}
    layers = project.get("layers") or []
    ui = project.get("ui") or {}

    # Normalized target capabilities
    caps = normalize_capabilities(target_meta or {})

    # Placeholder targets are not exportable (fail-closed)

    # Release contract: warn when exporting with an experimental target pack.
    try:
        if str((target_meta or {}).get("support_level") or "").lower() == "experimental":
            warnings.append("Target pack is EXPERIMENTAL (export contract not fully verified).")
    except Exception:
        pass

    if bool((target_meta or {}).get("placeholder")) or bool(caps.get("placeholder")):
        errors.append("Blocked: placeholder target pack (blocked until implemented).")

    supports_arduino_ino = bool(caps.get("supports_arduino_ino", True))
    supports_platformio = bool(caps.get("supports_platformio", True))
    allowed_led_backends = caps.get("led_backends") or []
    allowed_audio_backends = caps.get("audio_backends") or []

    supports_matrix = bool(caps.get("supports_matrix", False))

    # Release: enforce layout support by target capabilities.
    layout = (project or {}).get("layout") or {}
    shape = str(layout.get("shape", "strip") or "strip").lower()
    layout_kind = "matrix" if shape == "cells" else "strip"
    supports_strip = bool(caps.get("supports_strip", True))
    if layout_kind == "matrix" and (not supports_matrix):
        errors.append("Blocked: target pack does not support matrix/cells layout.")
    if layout_kind == "strip" and (not supports_strip):
        errors.append("Blocked: target pack does not support strip layout.")
    max_leds_hard = _as_int(caps.get("max_leds_hard"))
    max_leds_recommended = _as_int(caps.get("max_leds_recommended"))

    brightness_min = _as_int(caps.get("brightness_min"))
    brightness_max = _as_int(caps.get("brightness_max"))

    allowed_data_pins = caps.get("allowed_data_pins") or []
    allowed_msgeq7_reset_pins = caps.get("allowed_msgeq7_reset_pins") or []
    allowed_msgeq7_strobe_pins = caps.get("allowed_msgeq7_strobe_pins") or []
    allowed_msgeq7_left_pins = caps.get("allowed_msgeq7_left_pins") or []
    allowed_msgeq7_right_pins = caps.get("allowed_msgeq7_right_pins") or []

    # Backend-specific allowlists (optional, target-meta level)
    raw_caps = (target_meta or {}).get("capabilities") or {}
    allowed_led_types_by_backend = raw_caps.get("allowed_led_types_by_led_backend") or {}
    allowed_color_orders_by_backend = raw_caps.get("allowed_color_orders_by_led_backend") or {}

    # Requested selection (export section; fall back to UI if present)
    output_mode = str(export_cfg.get("output_mode") or "").strip().lower() or "arduino"

    led_backend_raw = str(export_cfg.get("led_backend") or "").strip()
    if not led_backend_raw and isinstance(ui, dict) and ui.get("export_led_backend"):
        led_backend_raw = str(ui.get("export_led_backend")).strip()
    audio_backend = str(export_cfg.get("audio_backend") or "").strip().lower()
    if not audio_backend and isinstance(ui, dict) and ui.get("export_audio_backend"):
        audio_backend = str(ui.get("export_audio_backend")).strip().lower()

    # If led_backend not specified, use first allowed backend (legacy default).
    if not led_backend_raw and allowed_led_backends:
        led_backend_raw = str(allowed_led_backends[0]).strip()
        warnings.append(f'Missing export.led_backend; defaulting to "{led_backend_raw}" for legacy project.')

    led_backend_lc = led_backend_raw.lower() if led_backend_raw else ""

    # legacy audio_backend policy: required only when audio_hw is present; otherwise default to none.
    aud_hw = export_cfg.get("audio_hw") or export_cfg.get("audio") or {}
    if "audio_backend" not in export_cfg and not (isinstance(ui, dict) and ui.get("export_audio_backend")):
        if isinstance(aud_hw, dict) and aud_hw:
            errors.append('Missing export.audio_backend (required when audio_hw is provided; set to "msgeq7" or "none").')
        else:
            warnings.append('Missing export.audio_backend; defaulting to "none" for legacy project.')
            audio_backend = "none"

    if output_mode not in ("arduino", "platformio"):
        errors.append(f"Invalid output_mode: {output_mode}")

    if output_mode == "arduino" and not supports_arduino_ino:
        errors.append("Target does not support Arduino .ino output.")
    if output_mode == "platformio" and not supports_platformio:
        errors.append("Target does not support PlatformIO output.")

    if allowed_led_backends and led_backend_raw:
        if led_backend_raw.lower() not in [str(x).lower() for x in allowed_led_backends]:
            errors.append(f"Target does not support led_backend '{led_backend_raw}'. Allowed: {', '.join(allowed_led_backends)}")
    if allowed_audio_backends and audio_backend:
        if audio_backend.lower() not in [str(x).lower() for x in allowed_audio_backends]:
            errors.append(f"Target does not support audio_backend '{audio_backend}'. Allowed: {', '.join(allowed_audio_backends)}")

    # Layout gates
    kind = str(layout.get("kind") or layout.get("shape") or "").strip().lower()
    led_count = _as_int(layout.get("led_count") or layout.get("num_leds"))

    if kind in ("matrix", "cells", "cell", "grid"):
        if not supports_matrix:
            errors.append("Target does not support matrix layout.")
        w = _as_int(layout.get("width") or layout.get("mw"))
        h = _as_int(layout.get("height") or layout.get("mh"))
        if w is None or h is None:
            errors.append("Matrix layout requires layout.width and layout.height.")
        else:
            if w <= 0 or h <= 0:
                errors.append("Matrix layout width/height must be > 0.")
            else:
                if led_count is not None and led_count != (w * h):
                    errors.append(f"Matrix led_count must equal width*height ({w*h}), got {led_count}.")
                led_count = w * h

    if led_count is None or led_count <= 0:
        errors.append("layout.led_count must be a positive integer.")
    else:
        if max_leds_hard is not None and led_count > max_leds_hard:
            errors.append(f"LED count {led_count} exceeds target hard limit {max_leds_hard}.")
        if max_leds_recommended is not None and led_count > max_leds_recommended:
            warnings.append(f"LED count {led_count} exceeds target recommended limit {max_leds_recommended}.")

    # Hardware gates
    hw = export_cfg.get("hw") or export_cfg.get("hardware") or {}
    if isinstance(hw, dict):
        b = _as_int(hw.get("brightness"))
        if b is not None:
            if brightness_min is not None and b < brightness_min:
                errors.append(f"Brightness {b} below target minimum {brightness_min}.")
            if brightness_max is not None and b > brightness_max:
                errors.append(f"Brightness {b} above target maximum {brightness_max}.")

        dp = _as_int(hw.get("data_pin"))
        if dp is not None and allowed_data_pins:
            allowed = set(_as_int(x) for x in allowed_data_pins if _as_int(x) is not None)
            if dp not in allowed:
                errors.append(f"Data pin {dp} is not allowed for this target.")

        # Backend-specific LED type / color order allowlists
        lt = str(hw.get("led_type") or "").strip()
        co = str(hw.get("color_order") or "").strip()
        # Target-wide LED type / color order allowlists (optional)
        tl = (target_meta or {}).get('led_types') or []
        tc = (target_meta or {}).get('color_orders') or []
        if isinstance(tl, list) and tl and lt and lt not in tl:
            errors.append(f"LED type '{lt}' is not allowed for this target.")
        if isinstance(tc, list) and tc and co and co not in tc:
            errors.append(f"Color order '{co}' is not allowed for this target.")


        def _lookup_ci(m: Dict[str, Any], key: str) -> Any:
            for k in m.keys():
                if str(k).lower() == key.lower():
                    return m.get(k)
            return None

        if led_backend_raw and isinstance(allowed_led_types_by_backend, dict) and lt:
            allowed_lt = _lookup_ci(allowed_led_types_by_backend, led_backend_raw)
            if isinstance(allowed_lt, list) and allowed_lt and lt not in allowed_lt:
                errors.append(f"LED type '{lt}' is not allowed for led_backend '{led_backend_raw}' on this target.")
        if led_backend_raw and isinstance(allowed_color_orders_by_backend, dict) and co:
            allowed_co = _lookup_ci(allowed_color_orders_by_backend, led_backend_raw)
            if isinstance(allowed_co, list) and allowed_co and co not in allowed_co:
                errors.append(f"Color order '{co}' is not allowed for led_backend '{led_backend_raw}' on this target.")

    # MSGEQ7 pin gates if requested
    if isinstance(aud_hw, dict) and audio_backend == "msgeq7":
        rp_raw = aud_hw.get("msgeq7_reset_pin")
        sp_raw = aud_hw.get("msgeq7_strobe_pin")
        lp_raw = aud_hw.get("msgeq7_left_pin")
        rrp_raw = aud_hw.get("msgeq7_right_pin")

        rp = _as_int(rp_raw)
        sp = _as_int(sp_raw)
        lp = _norm_pin(lp_raw)
        rrp = _norm_pin(rrp_raw)

        if rp is not None and allowed_msgeq7_reset_pins:
            allowed = set(_as_int(x) for x in allowed_msgeq7_reset_pins if _as_int(x) is not None)
            if rp not in allowed:
                errors.append(f"MSGEQ7 reset pin {rp_raw} is disallowed for this target.")
        if sp is not None and allowed_msgeq7_strobe_pins:
            allowed = set(_as_int(x) for x in allowed_msgeq7_strobe_pins if _as_int(x) is not None)
            if sp not in allowed:
                errors.append(f"MSGEQ7 strobe pin {sp_raw} is disallowed for this target.")

        if lp is not None and allowed_msgeq7_left_pins:
            allowed = set(_norm_pin(x) for x in allowed_msgeq7_left_pins if _norm_pin(x) is not None)
            if lp not in allowed:
                errors.append(f"MSGEQ7 left pin {lp_raw} is disallowed for this target.")
        if rrp is not None and allowed_msgeq7_right_pins:
            allowed = set(_norm_pin(x) for x in allowed_msgeq7_right_pins if _norm_pin(x) is not None)
            if rrp not in allowed:
                errors.append(f"MSGEQ7 right pin {rrp_raw} is disallowed for this target.")

    # Behavior eligibility
    # ------------------
    # NOTE: Parity is fail-closed for runtime subsystems. If a project *uses* a subsystem
    # (operators/postfx/rules/modulotion), the target must explicitly opt in.

    supports_operators_runtime = bool(caps.get("supports_operators_runtime", False))
    supports_postfx_runtime = bool(caps.get("supports_postfx_runtime", False))
    supports_rules_runtime = bool(caps.get("supports_rules_runtime", False))
    supports_modulation_runtime = bool(caps.get("supports_modulation_runtime", False))
    supports_modulation_export = bool(caps.get("supports_modulation_export", False))

    # Determine if project uses modulotors (layer-level modulation specs)
    uses_mods = False
    try:
        for ld in (layers or []):
            if not isinstance(ld, dict):
                continue
            mods = ld.get("modulotors")
            if isinstance(mods, list) and any(isinstance(m, dict) and bool(m.get("enabled", False)) for m in mods):
                uses_mods = True
                break
            params = ld.get("params")
            if isinstance(params, dict):
                ms = params.get("_mods")
                if isinstance(ms, list) and any(isinstance(m, dict) for m in ms):
                    uses_mods = True
                    break
    except Exception:
        uses_mods = False
    # If modulotors use audio sources, an audio backend must be available.
    uses_mods_audio = False
    try:
        for ld in (layers or []):
            if not isinstance(ld, dict):
                continue
            mods = ld.get("modulotors")
            if not isinstance(mods, list):
                continue
            for mm in mods:
                if not isinstance(mm, dict) or not bool(mm.get("enabled", False)):
                    continue
                src = str(mm.get("source") or "").strip().lower()
                if src in ("energy","audio_energy") or src.startswith("mono") or src.startswith("l") or src.startswith("r") or src.startswith("audio_"):
                    uses_mods_audio = True
                    break
            if uses_mods_audio:
                break
    except Exception:
        uses_mods_audio = False

    if uses_mods_audio and str(audio_backend or "").lower() == "none":
        errors.append("E_MODULOTORS_AUDIO_NEEDS_AUDIO_BACKEND: Modulotors use audio sources but target audio backend is NONEAUDIO.")


    if uses_mods and (not supports_modulation_runtime):
        errors.append("E_MODULOTORS_UNSUPPORTED: Project uses modulotors/modulation but target does not support modulation runtime.")
    supports_modulation_runtime = bool(caps.get("supports_modulation_runtime", supports_modulation_runtime))

    if uses_mods and (not supports_modulation_export):
        errors.append("E_MODULOTORS_EXPORT_UNSUPPORTED: Target does not support modulation export.")

    # Unknown signal references (rules/modulotors)
    # ------------------------------------------
    # We *detect* unknown signal ids, but only *block export* when the unknowns
    # are relevant to an otherwise-exportable runtime subsystem.
    #
    # Example: if a project contains legacy preview-only rule data but the target
    # does not support rules runtime, export is already blocked for rules; in
    # that case unknown signals are reported as warnings only.
    try:
        from export.exportable_surface import MODULATION_SOURCES_EXPORTABLE

        known = set(str(k) for k in (MODULATION_SOURCES_EXPORTABLE or []))

        # Include project variables as signal keys.
        vars_ = project.get("variables") if isinstance(project, dict) else None
        if isinstance(vars_, dict):
            for nm in (vars_.get("number") or {}).keys():
                known.add(f"vars.number.{nm}")
            for nm in (vars_.get("toggle") or {}).keys():
                known.add(f"vars.toggle.{nm}")

        def _norm_to_internal(s: str) -> str:
            s = str(s or "").strip()
            if not s:
                return s
            # Already internal ids
            if s in known:
                return s
            # Common normalized bus → internal ids
            if s.startswith("audio."):
                tail = s[6:]
                if tail == "energy":
                    return "audio_energy"
                if tail.startswith("mono") and tail[4:].isdigit():
                    return f"audio_mono{tail[4:]}"
                if (tail.startswith("L") or tail.startswith("l")) and tail[1:].isdigit():
                    return f"audio_L{tail[1:]}"
                if (tail.startswith("R") or tail.startswith("r")) and tail[1:].isdigit():
                    return f"audio_R{tail[1:]}"
                # beat/kick/snare/onset/bpm etc
                return "audio_" + tail.replace(".", "_")
            if s.startswith("purpose."):
                return "purpose_" + s.split(".", 1)[1]
            if s.startswith("lfo."):
                return "lfo_" + s.split(".", 1)[1]

            # Legacy forms
            if s.lower() == "energy":
                return "audio_energy"
            if s.lower().startswith("mono") and s[4:].isdigit():
                return f"audio_mono{s[4:]}"
            if (s.startswith("L") or s.startswith("l")) and s[1:].isdigit():
                return f"audio_L{s[1:]}"
            if (s.startswith("R") or s.startswith("r")) and s[1:].isdigit():
                return f"audio_R{s[1:]}"
            if s.startswith("audio_left_") and s[10:].isdigit():
                return f"audio_L{s[10:]}"
            if s.startswith("audio_right_") and s[11:].isdigit():
                return f"audio_R{s[11:]}"
            if s.startswith("purpose_f") and s[8:].isdigit():
                return s
            if s == "lfo_sine":
                return s
            return s

        refs = set()

        # Rules V6 refs
        rv6 = project.get("rules_v6") if isinstance(project, dict) else None
        uses_rules = bool(rv6) or bool(project.get("rules"))
        if isinstance(rv6, list):
            for r in rv6:
                if not isinstance(r, dict):
                    continue
                w = r.get("when")
                if isinstance(w, dict) and w.get("src") == "signal":
                    refs.add(str(w.get("signal") or ""))
                a = r.get("action")
                if isinstance(a, dict):
                    e = a.get("expr")
                    if isinstance(e, dict) and e.get("src") == "signal":
                        refs.add(str(e.get("signal") or ""))
                conds = r.get("conditions")
                if isinstance(conds, list):
                    for c in conds:
                        if isinstance(c, dict) and "signal" in c:
                            refs.add(str(c.get("signal") or ""))

        # Modulotor refs (support both modern 'modulotors' field and legacy params['_mods'])
        uses_mods = False
        if isinstance(layers, list):
            for ld in layers:
                if not isinstance(ld, dict):
                    continue
                mods = ld.get("modulotors")
                if isinstance(mods, list) and any(isinstance(m, dict) and bool(m.get("enabled", False)) for m in mods):
                    uses_mods = True
                    for m in mods:
                        if not isinstance(m, dict) or not bool(m.get("enabled", False)):
                            continue
                        refs.add(str(m.get("source") or m.get("signal") or ""))
                    continue
                params = ld.get("params")
                if isinstance(params, dict):
                    ms = params.get("_mods")
                    if isinstance(ms, list) and any(isinstance(m, dict) for m in ms):
                        uses_mods = True
                        for m in ms:
                            if not isinstance(m, dict):
                                continue
                            refs.add(str(m.get("source") or m.get("signal") or ""))

        unknown = []
        for s in sorted(refs):
            if not s:
                continue
            if s in known:
                continue
            ns = _norm_to_internal(s)
            if ns in known:
                continue
            # vars.* keys are accepted as-is
            if ns.startswith("vars."):
                continue
            unknown.append(s)

        if unknown:
            # Only block when the unknown signal(s) could affect an otherwise-exportable runtime path.
            blocks = ((uses_rules and supports_rules_runtime) or (uses_mods and supports_modulation_runtime))
            if blocks:
                errors.append("[E_UNKNOWN_SIGNALS_REQUIRED] Unknown signal id(s) referenced by exportable Rules/Modulotors: " + ", ".join(unknown))
            else:
                warnings.append("[W_UNKNOWN_SIGNALS_IGNORED] Unknown signal id(s) referenced, but affected subsystems are not exportable on this target: " + ", ".join(unknown))
    except Exception:
        # Unknown signal detection must never crash parity computation.
        pass

    # Operators usage
    any_ops = False
    for layer in layers:
        if not (isinstance(layer, dict) and isinstance(layer.get("operators"), list)):
            continue
        for op in (layer.get("operators") or []):
            if not isinstance(op, dict):
                continue
            if bool(op.get("enabled", True)) is False:
                continue
            k = str(op.get("type") or op.get("kind") or op.get("op") or "").strip().lower()
            if k in ("", "none", "solid"):
                continue
            any_ops = True
            break
        if any_ops:
            break
    if any_ops and not supports_operators_runtime:
        errors.append("Blocked: project uses Operators, but target does not support operators runtime.")

    # PostFX usage
    postfx = project.get("postfx") or {}
    pf_used = False
    if isinstance(postfx, dict):
        try:
            pf_used = (float(postfx.get("trail_amount", 0.0)) > 0.0) or (float(postfx.get("bleed_amount", 0.0)) > 0.0)
        except Exception:
            pf_used = True
    if pf_used and not supports_postfx_runtime:
        errors.append("Blocked: project uses PostFX (trail/bleed), but target does not support postfx runtime.")

    # Rules usage
    if (project.get("rules_v6") or project.get("rules")) and not supports_rules_runtime:
        errors.append("Blocked: project uses Rules, but target does not support rules runtime.")

    # Modulotion usage (layer.modulotors)
    any_mods = False
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        mods = layer.get("modulotors")
        if isinstance(mods, list):
            for m in mods:
                if isinstance(m, dict) and bool(m.get("enabled", False)):
                    any_mods = True
                    break
        if any_mods:
            break
    if any_mods and not supports_modulation_runtime:
        errors.append("Blocked: project uses Modulotors, but target does not support modulotion runtime.")

    for i, layer in enumerate(layers):
        if not isinstance(layer, dict):
            errors.append(f"Layer {i} is not an object.")
            continue
        beh = str(layer.get("behavior") or "").strip()
        nm = str(layer.get("name") or f"Layer {i}").strip()
        if not beh:
            errors.append(f"Layer '{nm}' missing behavior.")
        elif beh not in ELIGIBLE_BEHAVIORS:
            errors.append(f"Behavior '{beh}' is not export-eligible (layer '{nm}').")

    if output_mode == "platformio" and supports_platformio:
        suggestions.append("PlatformIO output will be emitted as a zipped project.")
    if output_mode == "arduino" and supports_arduino_ino:
        suggestions.append("Arduino output will be emitted as a single .ino file.")

    ok = len(errors) == 0
    return ParitySummary(ok=ok, errors=errors, warnings=warnings, suggestions=suggestions)


# ---------------------------------------------------------------------------
# Dict-based parity summary expected by Qt UI + Health Check report
# ---------------------------------------------------------------------------

_TARGET_ID_ALIASES = {
    # Legacy ids used by older UI/diagnostics.
    "arduino_export": "arduino_uno_fastled_msgeq7",
    "arduino": "arduino_uno_fastled_msgeq7",
}


def _find_target_meta(target_id: str | None) -> Dict[str, Any]:
    tid = str(target_id or "").strip() or "arduino_uno_fastled_msgeq7"
    tid = _TARGET_ID_ALIASES.get(tid, tid)
    for meta in list_targets():
        try:
            if meta.get("id") == tid:
                return meta
        except Exception:
            continue
    return {"id": tid, "name": tid, "placeholder": True}


def build_parity_summary(project: Dict[str, Any], target_id: str | None = None) -> Dict[str, Any]:
    """Return a dict parity summary used by UI/diagnostics.

    This is an adapter around the dataclass-based compute_export_parity_summary().
    It also produces a per-layer export status using export/export_eligibility.py
    and capabilities_catalog audio requirements.
    """
    project = project or {}
    tmeta = _find_target_meta(target_id)
    ps = compute_export_parity_summary(project, tmeta)

    # Requested backends (important for audio requirements)
    req = {}
    try:
        req = resolve_requested_backends(project, tmeta)
    except Exception:
        req = {"led_backend": "fastled", "audio_backend": "none"}
    audio_backend = str(req.get("audio_backend") or "none").strip().lower()

    led_backend = str(req.get("led_backend") or "fastled").strip().lower()
    # Enforce led backend allowed list (fail-closed if target restricts)
    try:
        if allowed_led_backends and led_backend and (led_backend not in [str(x).lower() for x in allowed_led_backends]):
            errors.append(f"Blocked: target pack does not support led backend '{led_backend}'. Allowed: {allowed_led_backends}")
    except Exception:
        pass


    # Capabilities catalog for requires_audio
    requires_audio_by_key: Dict[str, bool] = {}
    try:
        from behaviors.registry import load_capabilities_catalog
        cat = load_capabilities_catalog() or {}
        eff = (cat.get("effects") or {}) if isinstance(cat, dict) else {}
        for k, v in eff.items():
            if isinstance(v, dict):
                requires_audio_by_key[str(k)] = bool(v.get("requires_audio")) or ("audio" in (v.get("requires") or []))
    except Exception:
        requires_audio_by_key = {}

    layers_out: List[Dict[str, Any]] = []
    layers = project.get("layers") or []
    for i, layer in enumerate(layers if isinstance(layers, list) else []):
        if not isinstance(layer, dict):
            layers_out.append({"index": i, "status": "blocked", "reason": "Layer is not an object."})
            continue

        beh = str(layer.get("effect") or layer.get("behavior") or "").strip()
        elig = get_eligibility(beh)

        export_participates = beh not in NON_EXPORT_LAYER_EFFECTS

        # Base status from eligibility matrix
        status = str(elig.status or "preview-only")
        reason = str(elig.reason or "").strip()

        # Enforce audio requirement at export-config level (fail-closed)
        
    # Release: basic msgeq7 pin token sanity for non-AVR targets
    try:
        tid = str((target_meta or {}).get("id") or "")
        if str(audio_backend or "").lower() == "msgeq7" and tid.startswith("esp32"):
            left = str((aud_hw or {}).get("msgeq7_left_pin") or "")
            right = str((aud_hw or {}).get("msgeq7_right_pin") or "")
            if left.strip().upper().startswith("A") or right.strip().upper().startswith("A"):
                errors.append("MSGEQ7 pins look AVR-specific (A0/A1) for ESP32 target; set numeric GPIO ADC pins (e.g. 36/39).")
    except Exception:
        pass

if requires_audio_by_key.get(beh, False) and audio_backend in ("none", ""):
            status = ExportStatus.BLOCKED
            reason = (reason + " | " if reason else "") + "Requires audio, but export audio_backend is none."


        if not export_participates:
            status = "ignored"
            reason = (reason + " | " if reason else "") + "Preview utility; ignored for export."

        layers_out.append({"index": i,"enabled": bool(layer.get("enabled", True)),"behavior": beh,"status": status,"reason": reason,"export_participates": bool(export_participates)})

    # Determine export parity status based on ENABLED layers only.
    # Disabled layers are excluded from export and must not block parity.
    enabled_entries = [e for e in layers_out if e.get("enabled", True) and e.get("export_participates", True)]
    overall_ok = all(e.get("status") == ExportStatus.EXPORTABLE for e in enabled_entries)
    overall_status = "PASS" if overall_ok else "BLOCKED"
    return {
        "status": overall_status,
        "ok": overall_ok,
        "errors": list(ps.errors),
        "warnings": list(ps.warnings),
        "suggestions": list(ps.suggestions),
        "target": {"id": tmeta.get("id"), "name": tmeta.get("name")},
        "requested": req,
        "layers": layers_out,
    }


def layer_parity(ps: Dict[str, Any], layer_index: int) -> Dict[str, Any] | None:
    try:
        for ent in (ps.get("layers") or []):
            if ent.get("index") == layer_index:
                return ent
    except Exception:
        return None
    return None


def layer_tag_text(ps: Dict[str, Any], layer_index: int) -> str:
    ent = layer_parity(ps, layer_index) or {}
    st = str(ent.get("status") or "").strip() or "∅"
    if st == ExportStatus.EXPORTABLE:
        return "EXPORT"
    if st == ExportStatus.BLOCKED:
        return "BLOCK"
    if st == ExportStatus.PREVIEW_ONLY:
        return "PREVIEW"
    return st.upper()


def summarize_layers(ps: Dict[str, Any]) -> Dict[str, int]:
    counts = {ExportStatus.EXPORTABLE: 0, ExportStatus.BLOCKED: 0, ExportStatus.PREVIEW_ONLY: 0}
    try:
        for ent in (ps.get("layers") or []):
            st = str(ent.get("status") or "").strip()
            if st in counts:
                counts[st] += 1
    except Exception:
        pass
    return counts


def format_project_badge(ps: Dict[str, Any]) -> str:
    return "PASS" if bool(ps.get("ok")) else "BLOCKED"


def format_export_report_line(ps: Dict[str, Any]) -> str:
    # Concise single-line status for Export tab.
    st = format_project_badge(ps)
    c = summarize_layers(ps)
    return f"{st}  (exportable={c.get(ExportStatus.EXPORTABLE,0)} blocked={c.get(ExportStatus.BLOCKED,0)} preview={c.get(ExportStatus.PREVIEW_ONLY,0)})"


def format_export_block_message(ps: Dict[str, Any]) -> str:
    if bool(ps.get("ok")):
        return ""
    errs = ps.get("errors") or []
    if not errs:
        return "Export blocked."
    # Keep it short for UI; full list is in diagnostics.
    return "Export blocked: " + str(errs[0])

    # Release: if project requires audio but target selects audio_backend 'none', hard block.
    try:
        if requires_audio_by_key and str(selection.audio_backend or '').lower() == "none":
            errors.append("Project uses audio-reactive features but selected target audio backend is NONEAUDIO.")
    except Exception:
        pass

