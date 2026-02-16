"""Export gating (preview/export parity).

The goal: prevent 'preview-only' experiences.
If export would be unsafe or likely to fail for a selected target, block export and surface
the reason in both Export and Preview UI.

: Adds actionable suggestions so the user knows what to do next.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List
from export.export_eligibility import get_eligibility, ExportStatus

from .budget import estimate_project_budget_for_target


@dataclass(frozen=True)
class GateResult:
    ok: bool
    warnings: List[str]
    errors: List[str]
    suggestions: List[str]


def _suggest_from_limits(project: Dict[str, Any], target_meta: Dict[str, Any], errors: List[str], warnings: List[str]) -> List[str]:
    s: List[str] = []

    # Pull some stable project facts
    layout = (project or {}).get("layout") or {}
    shape = str(layout.get("shape", "strip") or "strip").lower()
    num_leds = int(layout.get("num_leds", 0) or 0)
    mw = int(layout.get("matrix_w", 0) or 0)
    mh = int(layout.get("matrix_h", 0) or 0)
    if shape == "cells" and mw and mh:
        num_leds = mw * mh

    ram_limit = int((target_meta or {}).get("ram_limit_bytes", 0) or 0)
    flash_limit = int((target_meta or {}).get("flash_limit_bytes", 0) or 0)

    # If RAM overflow is present, provide concrete options
    if any("Estimated RAM" in e for e in errors):
        if num_leds:
            s.append(f"Reduce LED count (current: {num_leds}). RAM scales with LEDs on many targets.")
        else:
            s.append("Reduce LED count. RAM usage scales with LEDs on many targets.")
        s.append("Switch to a target/board with more RAM (e.g., ESP32 variants), or use a target pack with PSRAM if available.")
        s.append("Use a more memory-efficient LED backend/driver if offered by the target pack.")
        s.append("Disable or simplify memory-heavy features (large palettes, many layers/effects) if your project uses them.")
    # If close to limits, nudge user
    if warnings and not errors:
        if ram_limit:
            s.append("If you hit limits later: pick a board with more RAM or reduce LED count.")
    # Generic advice
    if flash_limit:
        s.append("If flash becomes the blocker: reduce effect variety / code size, or choose a target with more flash.")

    # De-dupe while preserving order
    out: List[str] = []
    seen = set()
    for item in s:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return out


def gate_project_for_target(project: Dict[str, Any], target_meta: Dict[str, Any]) -> GateResult:
    """Return warnings/errors (+ suggestions) for exporting project to target."""
    warnings: List[str] = []
    errors: List[str] = []

    est = estimate_project_budget_for_target(project or {}, target_meta or {})
    for n in (est.notes or []):
        if ("hard limit" in n.lower()):
            errors.append(n)
        else:
            warnings.append(n)


    # PostFX runtime gating (preview/export parity)
    pf = (project or {}).get("postfx") or {}
    uses_postfx = False
    if isinstance(pf, dict) and pf:
        for k in ("trail_amount","bleed_amount","bleed_radius"):
            try:
                v = pf.get(k, 0)
                if v is None:
                    continue
                if float(v) != 0.0 and not (k=="bleed_radius" and float(v)==1.0):
                    # non-default amounts/radius implies PostFX used
                    uses_postfx = True
                    break
            except Exception:
                uses_postfx = True
                break
    if uses_postfx:
        caps = (target_meta or {}).get("capabilities") or {}
        if not bool(caps.get("supports_postfx_runtime", False)):
            errors.append("PostFX (trail/bleed) is used in this project, but the selected target does not support PostFX at runtime.")

    # Operators runtime gating (preview/export parity)
    # Operators are per-layer transforms (e.g., gain/gamma/posterize). Until a target explicitly
    # declares runtime support (and the emitter implements it), exporting a project that relies
    # on operators would be misleading.
    uses_operators = False
    try:
        for layer in (project or {}).get("layers") or []:
            ops = layer.get("operators")
            if not isinstance(ops, list):
                continue
            for op in ops:
                if not isinstance(op, dict):
                    continue
                if bool(op.get("enabled", True)) is False:
                    continue
                k = str(op.get("type") or op.get("kind") or op.get("op") or "").strip().lower()
                # Treat base/identity ops as not "using operators" for gating purposes.
                if k in ("", "none", "solid"):
                    continue
                uses_operators = True
                break
            if uses_operators:
                break
    except Exception:
        # fail-safe: if operator data is malformed, treat as used (truthful block)
        uses_operators = True

    if uses_operators:
        caps = (target_meta or {}).get("capabilities") or {}
        if not bool(caps.get("supports_operators_runtime", False)):
            errors.append("Operators are used in this project, but the selected target does not support operators at runtime.")

    suggestions = _suggest_from_limits(project or {}, target_meta or {}, errors, warnings)

    return GateResult(ok=(not errors), warnings=warnings, errors=errors, suggestions=suggestions)

# --- Step 1: Export Truth Enforcement ---

def ensure_exportable_behavior_key(behavior_key: str) -> None:
    """Raise RuntimeError if behavior is not explicitly exportable (fail-closed)."""
    elig = get_eligibility(behavior_key)
    if elig.status != ExportStatus.EXPORTABLE:
        reason = (elig.reason or "").strip() or "Not exportable"
        raise RuntimeError(f"Export blocked for behavior '{behavior_key}': {elig.status} — {reason}")

def ensure_exportable_project(project: dict) -> None:
    """Walk a project dict and fail loudly if any layer uses a blocked behavior."""
    layers = project.get("layers", []) or []
    for i, layer in enumerate(layers):
        beh = layer.get("behavior") or layer.get("behavior_key") or layer.get("effect") or ""
        if isinstance(beh, dict):
            beh = beh.get("key") or beh.get("id") or ""
        if beh:
            ensure_exportable_behavior_key(str(beh))
