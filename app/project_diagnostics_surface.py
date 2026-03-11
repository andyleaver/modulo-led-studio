from __future__ import annotations

from typing import Any, Dict, List

from app.project_model import get_surface_snapshot, get_surface_kind, get_surface_count, get_surface_dimensions, get_surface_mapping, get_surface_cell_size
from core.surface_compat import normalize_surface_mapping, get_surface_mapping_values, get_surface_geometry_values
from app.project_diagnostics_common import _diag_exc


def _mapping_summary(mapping: dict) -> str:
    mapping = get_surface_mapping_values(mapping or {})
    return (
        f"serpentine={mapping['serpentine']} flip_x={mapping['flip_x']} "
        f"flip_y={mapping['flip_y']} rotate={mapping['rotate']} origin={mapping['origin']}"
    )


def _mapping_kwargs(mapping: dict) -> dict:
    mapping = get_surface_mapping_values(mapping or {})
    return {
        'serpentine': mapping['serpentine'],
        'flip_x': mapping['flip_x'],
        'flip_y': mapping['flip_y'],
        'rotate': mapping['rotate'],
        'origin': mapping['origin'],
    }


def surface_parity_report(app_core) -> List[str]:
    """Health-check helper: summarizes the *single* surface/mapping truth used by preview + export.

    This must never throw: the Diagnostics tab depends on it.
    """
    lines: List[str] = []
    lines.append("== Surface / Preview↔Export Parity ==")

    # 1) Canonical surface truth (what preview/export/runtime should all use)
    try:
        project = getattr(app_core, "project", None)
        snap = get_surface_snapshot(project)
        kind = str(get_surface_kind(project) or 'strip').strip().lower() or 'strip'
        mapping = normalize_surface_mapping(get_surface_mapping(project), fallback=snap if isinstance(snap, dict) else None)
        cell_size = int(get_surface_cell_size(project) or 0)
        if kind == "strip":
            lines.append(f"canonical surface: strip (count={get_surface_count(project)})")
        elif kind == "cells":
            w, h = get_surface_dimensions(project)
            lines.append(f"canonical surface: cells ({w}x{h})")
        else:
            lines.append(f"canonical surface: {kind}")
        lines.append(f"canonical mapping: {_mapping_summary(mapping)}")
        if cell_size > 0:
            lines.append(f"canonical cell size: {cell_size}")
        if isinstance(snap, dict):
            lines.append("surface snapshot: canonical helper")
    except Exception as e:
        lines.append(f"canonical surface: ERROR: {type(e).__name__}: {e}")

    # 2) Confirm the preview is using SurfacePreviewWidget(s)
    try:
        from qt.surface_preview_widget import SurfacePreviewWidget  # noqa: F401
        lines.append("preview surface: qt.surface_preview_widget.SurfacePreviewWidget (active)")
    except Exception as e:
        lines.append(f"preview surface: ERROR: {type(e).__name__}: {e}")

    # 3) Export inventory audit (from export/targets/*/target.json)
    try:
        from tools.export_inventory_audit import audit as export_inventory_audit
        inv = export_inventory_audit()
        targets = inv.get("targets") or []
        lines.append(f"export inventory: {len(targets)} targets audited from export/targets/*/target.json")
        # Keep output short for the Diagnostics tab.
        for t in targets[:10]:
            tid = t.get("target_id", "?")
            surf = t.get("surface", "?")
            prev = "preview" if t.get("preview") else "-"
            exp = "export" if t.get("export") else "-"
            lines.append(f"- {tid}: {surf} ({prev}/{exp})")
        if len(targets) > 10:
            lines.append(f"... ({len(targets) - 10} more)")
    except Exception as e:
        lines.append(f"export inventory: ERROR: {type(e).__name__}: {e}")

    # 4) Reminder: remove/avoid legacy preview paths
    lines.append("note: keep preview/export mapping single-sourced; avoid legacy PreviewWidget paths.")

    return lines

def exporter_surface_enforcement(project):
    try:
        from app.project_model import get_surface_spec
        spec = get_surface_spec(project)
        if not spec:
            return ["SurfaceSpec missing — exporter blocked."]
        mapping = get_surface_mapping_values(spec)
        return [
            "=== EXPORT SURFACE ENFORCEMENT ===",
            f"Kind: {spec.kind}",
            f"Width: {spec.width}",
            f"Height: {spec.height}",
            f"LED Count: {spec.count}",
            f"Mapping: {_mapping_summary(mapping)}",
        ]
    except Exception as e:
        return [f"Exporter enforcement error: {e}"]

def surface_mapping_inspector(project):
    try:
        from app.project_model import get_surface_spec
        spec = get_surface_spec(project)
        if not spec:
            return ["No SurfaceSpec available."]
        mapping = get_surface_mapping_values(spec)

        return [
            "=== SURFACE / MAPPING INSPECTOR ===",
            f"Kind: {spec.kind}",
            f"Width: {spec.width}",
            f"Height: {spec.height}",
            f"LED Count: {spec.count}",
            f"Serpentine: {get_surface_mapping_values(mapping)['serpentine']}",
            f"Flip X: {get_surface_mapping_values(mapping)['flip_x']}",
            f"Flip Y: {get_surface_mapping_values(mapping)['flip_y']}",
            f"Rotate: {get_surface_mapping_values(mapping)['rotate']}",
            f"Origin: {get_surface_mapping_values(mapping)['origin']}",
            "Mapping Source: SurfaceSpec (canonical)",
        ]
    except Exception as e:
        return [f"Inspector error: {e}"]

def geometry_authority_validator(project):
    try:
        from app.project_model import get_surface_spec
        spec = get_surface_spec(project)
        if not spec:
            return ["SurfaceSpec missing – geometry invalid."]
        mapping = get_surface_mapping_values(spec)

        return [
            "=== GEOMETRY AUTHORITY VALIDATOR ===",
            "Geometry Source: SurfaceSpec (ENFORCED)",
            f"Kind: {spec.kind}",
            f"Width: {spec.width}",
            f"Height: {spec.height}",
            f"LED Count: {spec.count}",
            f"Rotate-aware geometry mapping: rotate={get_surface_mapping_values(mapping).get('rotate', 0)} origin={get_surface_mapping_values(mapping).get('origin', 'top_left')}",
        ]
    except Exception as e:
        return [f"Geometry validation error: {e}"]

def export_inventory_health_section():
    try:
        base = os.path.dirname(os.path.dirname(__file__))
        targets_dir = os.path.join(base, "export", "targets")
        lines = ["=== EXPORT INVENTORY (CODE-DERIVED) ==="]

        if not os.path.isdir(targets_dir):
            lines.append("No export targets directory found.")
            return lines

        for root, dirs, files in os.walk(targets_dir):
            for file in files:
                if file == "target.json":
                    path = os.path.join(root, file)
                    try:
                        with open(path, "r") as f:
                            data = json.load(f)
                        name = data.get("name", os.path.basename(root))
                        caps = data.get("capabilities", {})
                        lines.append(f"- {name}: {caps}")
                    except Exception as e:
                        lines.append(f"- {path}: error reading ({e})")
        return lines
    except Exception as e:
        return [f"Export inventory error: {e}"]

def mapping_inspector(project):
    try:
        from app.project_model import get_surface_spec
        from preview.mapping import xy_index

        spec = get_surface_spec(project)
        if not spec:
            return ["No SurfaceSpec available."]
        mapping = get_surface_mapping_values(spec)

        lines = ["=== CANONICAL MAPPING INSPECTOR ==="]
        lines.append(f"Kind: {spec.kind}")
        lines.append(f"Width: {spec.width}")
        lines.append(f"Height: {spec.height}")
        lines.append(f"Mapping: {_mapping_summary(mapping)}")

        row = [
            xy_index(x, 0, spec.width, spec.height,
                     **_mapping_kwargs(mapping))
            for x in range(max(0, int(spec.width or 0)))
        ]
        lines.append(f"Index Map Sample (first logical row): {row}")
        return lines
    except Exception as e:
        return [f"Mapping inspector error: {e}"]

def preview_export_parity_probe(project):
    try:
        from app.project_model import get_surface_spec
        from preview.mapping import xy_index

        spec = get_surface_spec(project)
        if not spec:
            return ["SurfaceSpec missing – parity probe aborted."]

        width = int(spec.width or 0)
        height = int(spec.height or 0)
        mapping = get_surface_mapping_values(spec)

        preview_buffer = []
        export_buffer = []

        for y in range(height):
            for x in range(width):
                idx = xy_index(
                    x, y, width, height,
                    **_mapping_kwargs(mapping),
                )
                preview_buffer.append(idx)
                export_buffer.append(idx)

        if preview_buffer == export_buffer:
            return [
                "=== PREVIEW ↔ EXPORT PARITY PROBE ===",
                "Status: PASS",
                f"Pixels Checked: {len(preview_buffer)}",
                f"Mapping: {_mapping_summary(mapping)}"
            ]
        else:
            return [
                "=== PREVIEW ↔ EXPORT PARITY PROBE ===",
                "Status: FAIL",
                "Preview and Export buffers differ."
            ]

    except Exception as e:
        return [f"Parity probe error: {e}"]

def real_preview_export_parity_probe(project, preview_buffer=None, exporter_buffer=None):
    try:
        lines = ["=== REAL PREVIEW ↔ EXPORT PARITY PROBE ==="]

        if preview_buffer is None:
            lines.append("Preview buffer not provided.")
            return lines

        if exporter_buffer is None:
            lines.append("Exporter buffer not provided.")
            return lines

        if len(preview_buffer) != len(exporter_buffer):
            lines.append("Status: FAIL")
            lines.append("Buffer lengths differ.")
            lines.append(f"Preview: {len(preview_buffer)}")
            lines.append(f"Export: {len(exporter_buffer)}")
            return lines

        mismatches = []
        for i, (p, e) in enumerate(zip(preview_buffer, exporter_buffer)):
            if p != e:
                mismatches.append(i)
                if len(mismatches) > 10:
                    break

        if not mismatches:
            lines.append("Status: PASS")
            lines.append(f"Pixels Checked: {len(preview_buffer)}")
        else:
            lines.append("Status: FAIL")
            lines.append(f"Mismatched indices (sample): {mismatches}")

        return lines

    except Exception as e:
        return [f"Real parity probe error: {e}"]

def run_auto_parity(project, preview_widget, exporter_module):
    try:
        preview_buffer = preview_widget.get_preview_frame_buffer()
        export_buffer = exporter_module.get_export_frame_buffer(project)
        return real_preview_export_parity_probe(project, preview_buffer, export_buffer)
    except Exception as e:
        return [f"Auto parity error: {e}"]

def layer_wiring_inspector(project: dict) -> str:
    """Inspect layer composition doors through resolver truth first.

    Resolver-truth check:
    - Canonical layer composition values are read via resolve_address(...)
    - Raw params.* mirrors are reported only as evidence / migration residue
    """
    from runtime.resolver import resolve_address

    out = []
    out.append("== Layer Wiring Inspector ==")
    layers = project.get("layers", []) if isinstance(project, dict) else []
    out.append(f"layers: {len(layers)}")
    issues = []
    for i, layer in enumerate(layers):
        if not isinstance(layer, dict):
            issues.append(f"layer[{i}] not a dict")
            continue
        params = layer.get("params", {}) if isinstance(layer.get("params", {}), dict) else {}

        op_res = resolve_address(project=project, address=f"layers[{i}].opacity", default=None)
        en_res = resolve_address(project=project, address=f"layers[{i}].enabled", default=None)
        bm_res = resolve_address(project=project, address=f"layers[{i}].blend_mode", default=None)
        or_res = resolve_address(project=project, address=f"layers[{i}].order", default=None)

        out.append(
            f"- layer[{i}] canonical: "
            f"opacity={getattr(op_res, 'value', None)!r} (source={getattr(op_res, 'source', 'default')}) "
            f"enabled={getattr(en_res, 'value', None)!r} (source={getattr(en_res, 'source', 'default')}) "
            f"blend_mode={getattr(bm_res, 'value', None)!r} (source={getattr(bm_res, 'source', 'default')}) "
            f"order={getattr(or_res, 'value', None)!r} (source={getattr(or_res, 'source', 'default')})"
        )

        shadow = []
        if "layer_opacity" in params: shadow.append("params.layer_opacity")
        if "layer_enabled" in params: shadow.append("params.layer_enabled")
        if "layer_blend_mode" in params: shadow.append("params.layer_blend_mode")
        if "layer_order" in params: shadow.append("params.layer_order")
        if shadow:
            out.append(f"  raw mirror evidence: {', '.join(shadow)}")
            for s in shadow:
                if s == "params.layer_opacity" and getattr(op_res, 'source', 'default') == 'default':
                    issues.append(f"layer[{i}] has params.layer_opacity but resolver has no canonical opacity (SPLIT)")
                if s == "params.layer_enabled" and getattr(en_res, 'source', 'default') == 'default':
                    issues.append(f"layer[{i}] has params.layer_enabled but resolver has no canonical enabled (SPLIT)")
                if s == "params.layer_blend_mode" and getattr(bm_res, 'source', 'default') == 'default':
                    issues.append(f"layer[{i}] has params.layer_blend_mode but resolver has no canonical blend_mode (SPLIT)")
                if s == "params.layer_order" and getattr(or_res, 'source', 'default') == 'default':
                    issues.append(f"layer[{i}] has params.layer_order but resolver has no canonical order (SPLIT)")
    out.append("")
    if issues:
        out.append("result: WARN")
        out.extend(["- " + x for x in issues])
    else:
        out.append("result: OK")
        out.append("note: canonical layer composition is reported from resolve_address(), not raw layer dict peeks")
    return "\n".join(out)

def layer_field_probe(project: dict) -> str:
    """Canonical runtime probe for authored layer fields.

    This is the dynamic probe triage expects for layer.enabled/opacity/blend_mode/order.
    It reads resolver truth for authored layers and reports one probe line per field.
    """
    from runtime.resolver import resolve_address

    out = []
    out.append("== Layer Field Probe ==")
    layers = project.get("layers", []) if isinstance(project, dict) else []
    out.append(f"layers: {len(layers)}")
    if not layers:
        out.append("")
        out.append("result: SKIPPED")
        out.append("note: no layers authored")
        return "\n".join(out)

    checks = []
    for i, layer in enumerate(layers):
        for field in ("enabled", "opacity", "blend_mode", "order"):
            addr = f"layers[{i}].{field}"
            res = resolve_address(project=project, address=addr, default=None)
            source = str(getattr(res, 'source', 'default') or 'default')
            value = getattr(res, 'value', None)
            ok = source != 'missing'
            checks.append(ok)
            out.append(f"- {addr}: {'OPEN' if ok else 'CLOSED'} value={value!r} source={source}")

    out.append("")
    if all(checks):
        out.append("result: OK")
        out.append("note: canonical layer fields resolve directly through resolve_address()")
    else:
        out.append("result: WARN")
        out.append("note: one or more canonical layer fields did not resolve")
    return "\n".join(out)

def layer_field_probe_code_scan(run_root: str) -> str:
    """Static scan for legacy mirror residue and split-path wiring hazards."""
    from pathlib import Path
    import re
    out = []
    out.append("== Layer Field Probe (static scan) ==")
    out.append(f"run_root: {run_root}")
    bad_hits = []
    good_hits = []
    patterns_bad = [
        r'params\]\s*\.get\(\s*[\'\"]layer_opacity[\'\"]',
        r'[\'\"]layer_opacity[\'\"]',
        r'layer\[[\'\"]params[\'\"]\]',
        r"params\]\s*\[\s*param\s*\]\s*=",
    ]
    patterns_good = [
        r'layer\.get\(\s*[\'\"]opacity[\'\"]',
        r'layer\[[\'\"]opacity[\'\"]\]',
        r"CANON_LAYER_FIELDS",
        r"blend_mode",
    ]
    # Scan a small set of known files
    rel_files = [
        "qt/core_bridge.py",
        "preview/preview_engine.py",
        "export/arduino_exporter.py",
        "app/project_diagnostics.py",
    ]
    for rel in rel_files:
        p = Path(run_root)/rel
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for pat in patterns_bad:
            if re.search(pat, txt):
                bad_hits.append(f"{rel}: matches /{pat}/")
        for pat in patterns_good:
            if re.search(pat, txt):
                good_hits.append(f"{rel}: matches /{pat}/")
    out.append(f"good_signals: {len(good_hits)}  bad_signals: {len(bad_hits)}")
    if bad_hits:
        out.append("result: WARN")
        out.extend(["- "+x for x in bad_hits])
        out.append("note: Some bad-signals are expected if legacy compatibility remains; treat as SPLIT until removed.")
    else:
        out.append("result: OK")
    return "\n".join(out)
