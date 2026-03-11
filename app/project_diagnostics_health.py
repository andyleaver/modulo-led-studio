from __future__ import annotations

from typing import Any, Dict, List, Set

from app.masks_resolver import resolve_mask_to_indices
from app.project_validation import validate_project
from runtime.resolver import resolve_address

from app.project_diagnostics_common import _collect_mask_refs, _diag_exc, _layout_count


def diagnose_project(project: Dict[str, Any]) -> Dict[str, List[str]]:
    """Return {'invalid': [...], 'dangling': [...], 'empty': [...]}."""
    p = project if isinstance(project, dict) else {}
    n = _layout_count(p)

    invalid: List[str] = []
    dangling: List[str] = []
    empty: List[str] = []

    # ---- invalid (validator is authoritative) ----
    snap = validate_project(p)
    for e in (snap.get("errors") or []):
        invalid.append(str(e))
    for w in (snap.get("warnings") or []):
        # warnings still reduce overall health visibility
        invalid.append(str(w))

    zones = p.get("zones") or {}
    if isinstance(zones, dict):
        for k in sorted(zones.keys(), key=lambda s: str(s).lower()):
            node = zones.get(k) or {}
            if isinstance(node, dict):
                idx = node.get("indices")
                has_range = (node.get('start') is not None and node.get('end') is not None)
                if (not has_range) and isinstance(idx, list) and len(idx) == 0:
                    empty.append(f"zone '{k}': empty indices")

    groups = p.get("groups") or {}
    if isinstance(groups, dict):
        for k in sorted(groups.keys(), key=lambda s: str(s).lower()):
            node = groups.get(k) or {}
            if isinstance(node, dict):
                idx = node.get("indices")
                if isinstance(idx, list) and len(idx) == 0:
                    empty.append(f"group '{k}': empty indices")

    masks = p.get("masks") or {}
    if isinstance(masks, dict):
        # ---- mask namespace invariants (A1) ----
        # Stored masks must be true mask defs only. Any ':' belongs to a target reference
        # (e.g. zone:NAME / group:NAME) and must not be persisted as a mask key.
        for mk in sorted(masks.keys(), key=lambda s: str(s).lower()):
            try:
                if isinstance(mk, str) and ":" in mk:
                    invalid.append(f"mask '{mk}': invalid key (contains ':')")
            except Exception as e:
                _diag_exc(e, "app/project_diagnostics.py")

        # Warn if a mask key shadows a group key (ambiguous authoring intent).
        groups = p.get("groups") or {}
        if isinstance(groups, dict):
            for mk in sorted(masks.keys(), key=lambda s: str(s).lower()):
                try:
                    if isinstance(mk, str) and mk in groups:
                        invalid.append(
                            f"mask '{mk}': shadows group '{mk}' (use group:{mk} when targeting)"
                        )
                except Exception as e:
                    _diag_exc(e, "app/project_diagnostics.py")

        # Empty masks (resolve ok but selects nothing)
        for mk in sorted(masks.keys(), key=lambda s: str(s).lower()):
            try:
                s = resolve_mask_to_indices(p, str(mk), n=n)
                if len(s) == 0:
                    empty.append(f"mask '{mk}': resolves to empty")
            except Exception as e:
                invalid.append(f"mask '{mk}': {e}")

        # Dangling refs inside composed masks
        all_keys = set(str(k) for k in masks.keys())
        for mk in sorted(masks.keys(), key=lambda s: str(s).lower()):
            refs: Set[str] = set()
            _collect_mask_refs(masks.get(mk), refs)
            for r in sorted(refs):
                if r not in all_keys:
                    dangling.append(f"mask '{mk}': references missing mask '{r}'")

    # Dangling UI target mask key
    try:
        tm = resolve_address(project=p, address="project.ui.target_mask", default=None).value
    except Exception:
        tm = None
    if tm is not None and str(tm).strip():
        tm = str(tm)
        if not isinstance(masks, dict) or tm not in (masks or {}):
            dangling.append(f"ui.target_mask '{tm}': missing")

    # Dangling layer targets (zone/group index points past current list)
    layers = p.get("layers")
    if isinstance(layers, list):
        zkeys = sorted(list(zones.keys())) if isinstance(zones, dict) else []
        gkeys = sorted(list(groups.keys())) if isinstance(groups, dict) else []
        for i, L in enumerate(layers):
            if not isinstance(L, dict):
                continue
            tk = str(L.get("target_kind", "all") or "all").lower().strip()
            try:
                tr = int(L.get("target_ref", 0) or 0)
            except Exception:
                tr = 0
            if tk == "zone" and not (0 <= tr < len(zkeys)):
                dangling.append(f"Layer[{i}] target_kind=zone target_ref={tr}: out of range (zones={len(zkeys)})")
            if tk == "group" and not (0 <= tr < len(gkeys)):
                dangling.append(f"Layer[{i}] target_kind=group target_ref={tr}: out of range (groups={len(gkeys)})")


    # ---- namespace invariants (A1) ----
    # Names must be simple keys (no ":"), non-empty, and unique across zones/masks/groups.
    def _bad_key(k: str) -> bool:
        return (not k) or (k.strip() != k) or (":" in k)

    zks = list(zones.keys()) if isinstance(zones, dict) else []
    gks = list(groups.keys()) if isinstance(groups, dict) else []
    mks = list(masks.keys()) if isinstance(masks, dict) else []

    for k in sorted(set(zks)):
        if _bad_key(str(k)):
            invalid.append(f"zone key '{k}': invalid (no colon, no leading/trailing spaces, non-empty)")
    for k in sorted(set(gks)):
        if _bad_key(str(k)):
            invalid.append(f"group key '{k}': invalid (no colon, no leading/trailing spaces, non-empty)")
    for k in sorted(set(mks)):
        if _bad_key(str(k)):
            invalid.append(f"mask key '{k}': invalid (no colon, no leading/trailing spaces, non-empty)")

    collisions: Set[str] = set(zks) & set(gks) | set(zks) & set(mks) | set(gks) & set(mks)
    for k in sorted(collisions):
        invalid.append(f"entity key '{k}': collision across zones/masks/groups (must be unique)")

    # ---- operator target key sanity (A1) ----
    # Any operator with target_kind+target_key must point at an existing entity.
    if isinstance(layers, list):
        for li, L in enumerate(layers):
            if not isinstance(L, dict):
                continue
            ops = L.get("operators")
            if not isinstance(ops, list):
                continue
            for oi, op in enumerate(ops):
                if not isinstance(op, dict):
                    continue
                tk = op.get("target_kind")
                tkey = op.get("target_key")
                if tk is None or tkey is None:
                    continue
                tk_s = str(tk).lower().strip()
                tkey_s = str(tkey)
                if tk_s == "mask" and (not isinstance(masks, dict) or tkey_s not in masks):
                    dangling.append(f"Layer[{li}].Op[{oi}] target=mask:{tkey_s}: missing")
                if tk_s == "group" and (not isinstance(groups, dict) or tkey_s not in groups):
                    dangling.append(f"Layer[{li}].Op[{oi}] target=group:{tkey_s}: missing")
                if tk_s == "zone" and (not isinstance(zones, dict) or tkey_s not in zones):
                    dangling.append(f"Layer[{li}].Op[{oi}] target=zone:{tkey_s}: missing")
    return {"invalid": invalid, "dangling": dangling, "empty": empty}

def diagnostics_text(project: Dict[str, Any]) -> str:
    """Human-readable multiline diagnostics."""
    d = diagnose_project(project)
    lines: List[str] = []

    def emit(section: str, items: List[str]) -> None:
        if not items:
            return
        lines.append(section)
        for s in items:
            lines.append(f"  - {s}")
        lines.append("")

    emit("INVALID", d.get("invalid") or [])
    emit("DANGLING", d.get("dangling") or [])
    emit("EMPTY", d.get("empty") or [])

    if not lines:
        return "OK — no empty/invalid/dangling issues detected."

    # trim trailing blank
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)

def run_full_health_check(
    project: Dict[str, Any],
    app_core=None,
    controller=None,
    include_audio: bool = True,
) -> str:
    """Generate the classic multi-section health report.

    This is the stable entry-point used by the Qt Diagnostics tab.
    It must stay robust even if UI files are split/renamed.
    """
    import sys
    import datetime as _dt
    from pathlib import Path

    from app.app_identity import get_app_id
    from app.project_validation import validate_project

    ts = _dt.datetime.now(_dt.timezone.utc).isoformat().replace('+00:00', 'Z')
    try:
        argv0 = sys.argv[0]
    except Exception:
        argv0 = ""
    try:
        run_root = str(Path(argv0).resolve().parent) if argv0 else ""
    except Exception:
        run_root = ""

    app_id = get_app_id(Path(__file__))

    # ---- project validation ----
    snap = validate_project(project if isinstance(project, dict) else {})
    errors = snap.get("errors") or []
    warnings = snap.get("warnings") or []

    # ---- structural diagnostics ----
    struct = diagnose_project(project if isinstance(project, dict) else {})
    invalid = struct.get("invalid") or []
    dangling = struct.get("dangling") or []
    empty = struct.get("empty") or []

    # ---- operators sanity (lightweight) ----
    ops_total = 0
    ops_enabled = 0
    ops_issues = 0
    try:
        layers = (project or {}).get("layers") or []
        if isinstance(layers, list):
            for L in layers:
                if not isinstance(L, dict):
                    continue
                ops = L.get("operators") or []
                if not isinstance(ops, list):
                    continue
                for op in ops:
                    ops_total += 1
                    if isinstance(op, dict) and bool(op.get("enabled", True)):
                        ops_enabled += 1
                    if (not isinstance(op, dict)) or (not str(op.get("kind") or op.get("type") or "").strip()):
                        ops_issues += 1
    except Exception as e:
        _diag_exc(e, "app/project_diagnostics.py")

    # ---- startup/recovery snapshot (best effort) ----
    startup_source = "unknown"
    recovery_status = {}
    try:
        candidates = []
        if controller is not None:
            candidates.append(getattr(controller, "bridge", None))
            candidates.append(controller)
        if app_core is not None:
            candidates.append(getattr(app_core, "bridge", None))
            candidates.append(app_core)

        startup_recovery_meta = {}
        for c in candidates:
            if c is None:
                continue
            ss = getattr(c, "startup_source", None)
            rs = getattr(c, "startup_recovery_status", None)
            if isinstance(ss, str) and ss.strip():
                startup_source = ss.strip()
            if isinstance(rs, dict) and rs:
                startup_recovery_meta = dict(rs)
            if startup_source != "unknown" or startup_recovery_meta:
                break

        from app.autosave import get_recovery_status
        live_recovery_status = get_recovery_status()
        if startup_recovery_meta:
            recovery_status = dict(live_recovery_status)
            for key in (
                "used_source",
                "used_path",
                "primary_mtime",
                "backup_mtime",
                "primary_path",
                "backup_path",
            ):
                value = startup_recovery_meta.get(key)
                if value not in (None, ""):
                    recovery_status[key] = value
        else:
            recovery_status = live_recovery_status
    except Exception as e:
        _diag_exc(e, "app/project_diagnostics.py")

    # ---- audio snapshot (best effort) ----
    audio_mode = "sim"
    audio_backend = "unknown"
    audio_status = "SKIPPED" if not include_audio else "UNKNOWN"
    audio_energy = None
    audio_mono = None
    signal_frame = None

    try:
        if not include_audio:
            raise Exception("audio skipped")
        # The Qt app sometimes passes CoreBridge as app_core directly (no .bridge).
        # Probe a small set of likely holders for preview-audio fields.
        candidates = []
        if controller is not None:
            candidates.append(getattr(controller, "bridge", None))
            candidates.append(controller)
        if app_core is not None:
            candidates.append(getattr(app_core, "bridge", None))
            candidates.append(app_core)

        def has_preview_fields(o) -> bool:
            return o is not None and (
                hasattr(o, "preview_audio_backend")
                or hasattr(o, "preview_audio_status")
                or hasattr(o, "preview_audio_mode")
                or hasattr(o, "preview_engine")
            )

        holder = None
        for c in candidates:
            if has_preview_fields(c):
                holder = c
                break

        if holder is not None:
            audio_mode = str(getattr(holder, "preview_audio_mode", audio_mode))
            audio_backend = str(getattr(holder, "preview_audio_backend", audio_backend))
            audio_status = str(getattr(holder, "preview_audio_status", audio_status))

            eng = getattr(holder, "preview_engine", None)
            st = getattr(eng, "last_audio_state", None) if eng is not None else None
            if isinstance(st, dict):
                audio_energy = st.get("energy")
                audio_mono = st.get("mono")
                try:
                    sb = getattr(eng, "signal_bus", None)
                    signal_frame = getattr(sb, "frame", None) if sb is not None else None
                except Exception:
                    signal_frame = None
    except Exception as e:
        _diag_exc(e, "app/project_diagnostics.py")

    lines: List[str] = []
    lines.append("=== HEALTH CHECK REPORT ===")
    lines.append(f"timestamp: {ts}")
    lines.append(f"run_argv0: {argv0}")
    if run_root:
        lines.append(f"run_root: {run_root}")
    lines.append(f"app_id: {app_id}")
    lines.append("")

    lines.append("== Project Validation ==")
    lines.append(f"errors: {len(errors)}")
    lines.append(f"warnings: {len(warnings)}")
    if errors:
        lines.append("errors_detail:")
        for e in errors[:50]:
            lines.append(f"  - {e}")
    if warnings:
        lines.append("warnings_detail:")
        for w in warnings[:50]:
            lines.append(f"  - {w}")
    lines.append("")

    lines.append("== Structural Diagnostics (Zones/Masks/Groups) ==")
    lines.append(f"invalid: {len(invalid)}")
    lines.append(f"dangling: {len(dangling)}")
    lines.append(f"empty: {len(empty)}")
    for tag, items in [("invalid", invalid), ("dangling", dangling), ("empty", empty)]:
        if items:
            lines.append(f"{tag}_detail:")
            for s in items[:50]:
                lines.append(f"  - {s}")
    lines.append("")

    lines.append("== Operators Sanity ==")
    lines.append(f"operators_total: {ops_total} (enabled: {ops_enabled})")
    lines.append(f"issues: {ops_issues}")
    lines.append("")

    lines.append("== Startup / Recovery ==")
    lines.append(f"startup_source: {startup_source}")
    if isinstance(recovery_status, dict) and recovery_status:
        lines.append(f"recovery.enabled: {bool(recovery_status.get('enabled'))}")
        lines.append(f"recovery.start_clean: {bool(recovery_status.get('start_clean'))}")
        lines.append(f"recovery.primary_exists: {bool(recovery_status.get('primary_exists'))}")
        lines.append(f"recovery.backup_exists: {bool(recovery_status.get('backup_exists'))}")
        used_source = str(recovery_status.get('used_source') or '').strip()
        used_path = str(recovery_status.get('used_path') or '').strip()
        primary_path = str(recovery_status.get('primary_path') or '').strip()
        backup_path = str(recovery_status.get('backup_path') or '').strip()
        primary_mtime = str(recovery_status.get('primary_mtime') or '').strip()
        backup_mtime = str(recovery_status.get('backup_mtime') or '').strip()
        if used_source:
            lines.append(f"recovery.used_source: {used_source}")
        if used_path:
            lines.append(f"recovery.used_path: {used_path}")
        if primary_mtime:
            lines.append(f"recovery.primary_mtime: {primary_mtime}")
        if backup_mtime:
            lines.append(f"recovery.backup_mtime: {backup_mtime}")
        if primary_path:
            lines.append(f"recovery.primary_path: {primary_path}")
        if backup_path:
            lines.append(f"recovery.backup_path: {backup_path}")
    else:
        lines.append("recovery: unavailable")
    lines.append("")

    out = lines

    # Surface/Mapping Parity
    try:
        from app.mapping_parity_probe import run_mapping_parity_probe, dump_surface_mapping, run_mapping_parity_sweep
        out.append('')
        out.append('== Surface/Mapping Inspector ==')
        out.append(dump_surface_mapping(project))
        out.append('')
        out.append('== Surface/Mapping Parity ==')
        out.append('note: compares preview canonical mapping vs export-like mapping functions')
        report = run_mapping_parity_probe(project, mode='quick')
        out.extend(report.splitlines())
        out.append('')
        out.append('== Surface/Mapping Parity Sweep ==')
        sweep = run_mapping_parity_sweep(project)
        # keep sweep short in health check (first ~120 lines)
        s_lines = sweep.splitlines()
        if len(s_lines) > 120:
            s_lines = s_lines[:120] + ['... (truncated)']
        out.extend(s_lines)
    except Exception as e:
        out.append('')
        out.append('== Surface/Mapping Diagnostics ==')
        out.append(f'ERROR: {e}')
    # --- end Surface/Mapping Parity ---


    # Layer Field Parity
    try:
        out.append('')
        out.append('== Layer Field Parity ==')
        from runtime.resolver import resolve_address
        layers = project.get('layers', []) if isinstance(project, dict) else []
        issues = []
        for li, layer in enumerate(layers):
            if not isinstance(layer, dict):
                continue
            params = layer.get('params', {}) if isinstance(layer.get('params', {}), dict) else {}
            op_res = resolve_address(project=project, address=f"layers[{li}].opacity", default=None).value
            en_res = resolve_address(project=project, address=f"layers[{li}].enabled", default=True).value
            bm_res = resolve_address(project=project, address=f"layers[{li}].blend_mode", default='over').value
            if 'layer_opacity' in params and op_res is None:
                issues.append(f"layer[{li}] has params.layer_opacity but resolver has no canonical layers[i].opacity (SPLIT)")
            if op_res is not None:
                try: float(op_res)
                except Exception: issues.append(f"layer[{li}].opacity not numeric via canonical resolver")
            if not isinstance(en_res, (bool, int)):
                issues.append(f"layer[{li}].enabled not bool via canonical resolver")
            if bm_res is not None and not isinstance(bm_res, str):
                issues.append(f"layer[{li}].blend_mode not str via canonical resolver")
        if issues:
            out.append('result: WARN')
            out.extend(['- '+x for x in issues])
        else:
            out.append('result: OK')
            out.append('note: canonical fields are layers[i].opacity / layers[i].enabled / layers[i].blend_mode')
    except Exception as e:
        out.append('')
        out.append('== Layer Field Parity ==')
        out.append(f'ERROR: {e}')
    # --- end Layer Field Parity ---

    lines.append("== Audio Snapshot ==")
    lines.append(f"mode: {audio_mode}")
    lines.append(f"backend: {audio_backend}")
    lines.append(f"status: {audio_status}")
    if signal_frame is not None:
        lines.append(f"signal_bus.frame: {signal_frame}")
    if audio_energy is not None:
        lines.append(f"audio.energy: {audio_energy}")
    if audio_mono is not None:
        try:
            lines.append(f"audio.mono: {list(audio_mono)[:7]}")
        except Exception:
            lines.append(f"audio.mono: {audio_mono}")
    lines.append("")

    lines.append("== Diagnostics Wiring (code pointers) ==")
    lines.append("Diagnostics surface: qt/diagnostics_console.py (attached console)")
    lines.append("Health report: app/project_diagnostics.py::run_full_health_check")
    lines.append("Structural checks: app/project_diagnostics.py::diagnose_project")
    lines.append("Effect audit: app/effect_audit.py")
    lines.append("")

    return "\n".join(lines)
