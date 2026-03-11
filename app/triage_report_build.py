from __future__ import annotations

"""Canonical triage summary.

Purpose:
- give a single, opinionated OPEN / SPLIT / CLOSED view from the canonical checkpoint
- speak in terms of canonical domains instead of scattered probe names
- surface next actions without reintroducing legacy identifiers as live targets
- group proof debt by canonical probe so triage yields a concrete action plan
"""

from collections import OrderedDict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.project_diagnostics import (
    diagnose_project,
    layer_wiring_inspector,
    preview_export_parity_probe,
    surface_mapping_inspector,
)
from app.project_model import get_surface_spec
from app.app_identity import APP_ID
from runtime.canonical_addr import canonical_registry
from runtime.resolver import resolve_address

Status = str

TRIAGE_ADDRESS_MATRIX: List[str] = [
    "project.surface.kind",
    "project.surface.count",
    "project.surface.width",
    "project.surface.height",
    "project.surface.mapping.serpentine",
    "project.postfx.trail_amount",
    "project.postfx.bleed_amount",
    "project.postfx.bleed_radius",
    "project.spatial.enabled",
    "project.spatial.world_scale",
]

def _iter_triage_addresses(project: Dict[str, Any], runtime: Optional[Dict[str, Any]] = None) -> List[str]:
    addrs: List[str] = list(TRIAGE_ADDRESS_MATRIX)
    layers = project.get("layers") or []
    if layers:
        addrs.extend([
            "layers[0].enabled",
            "layers[0].opacity",
            "layers[0].blend_mode",
            "layers[0].order",
            "layers[0]._op_overrides.gain",
            "layers[0]._op_overrides.gamma",
        ])
    vars_dict = project.get("variables") or {}
    if isinstance(vars_dict, dict):
        num = vars_dict.get("number") or {}
        tog = vars_dict.get("toggle") or {}
        if isinstance(num, dict):
            for name in sorted(num.keys())[:2]:
                addrs.append(f"project.variables.number.{name}")
        if isinstance(tog, dict):
            for name in sorted(tog.keys())[:2]:
                addrs.append(f"project.variables.toggle.{name}")
    sigs = (runtime or {}).get("signals") or {}
    if isinstance(sigs, dict):
        for key in sorted(sigs.keys())[:2]:
            addrs.append(f"signals.{key}")
    return addrs

def _templated_registry_key(addr: str) -> str:
    if addr.startswith("layers["):
        return addr.replace("[0]", "[*]", 1)
    if addr.startswith("project.variables.number."):
        return "project.variables.number.*"
    if addr.startswith("project.variables.toggle."):
        return "project.variables.toggle.*"
    if addr.startswith("signals."):
        return "signals.*"
    if addr.startswith("systems.particles.") and addr.endswith(".count"):
        return "systems.particles.*.count"
    if addr.startswith("systems.particles.") and addr.endswith(".max_particles"):
        return "systems.particles.*.max_particles"
    return addr

def _domain_for_address(addr: str) -> str:
    if addr.startswith("project.surface."):
        return "surface_mapping"
    if addr.startswith("project.postfx.") or addr.startswith("layers["):
        return "composition"
    if addr.startswith("project.variables.") or addr.startswith("signals.") or addr.startswith("systems.") or addr.startswith("project.spatial."):
        return "runtime_domains"
    return "canonical_resolver"

def _support_map(scope: str) -> Dict[str, bool]:
    """Best-effort canonical support map by address family.

    This is intentionally conservative: triage should expose likely parity seams,
    not claim universal support where the canonical path is not yet proven.
    """
    if scope in ("layer_field", "project_postfx", "project_layout"):
        return {"authored": True, "preview": True, "export": True, "runtime": True}
    if scope == "operator_param":
        return {"authored": False, "preview": True, "export": True, "runtime": True}
    if scope in ("project_variable",):
        return {"authored": True, "preview": False, "export": False, "runtime": True}
    if scope in ("signal", "system_state"):
        return {"authored": False, "preview": False, "export": False, "runtime": True}
    if scope in ("project_spatial",):
        return {"authored": True, "preview": False, "export": False, "runtime": True}
    return {"authored": False, "preview": False, "export": False, "runtime": False}

def _support_matrix_text(bits: Dict[str, bool]) -> str:
    return "/".join(name for name in ("authored", "preview", "export", "runtime") if bits.get(name)) or "none"

def _address_evidence_and_confidence(addr: str, meta: Dict[str, Any], source: str, support_bits: Dict[str, bool], status: str, runtime: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
    parts: List[str] = []
    if meta:
        parts.append("registry")
    if source not in ("default", "missing"):
        parts.append(f"resolver:{source}")
    if support_bits.get("authored"):
        parts.append("authored")
    if support_bits.get("preview"):
        parts.append("preview")
    if support_bits.get("export"):
        parts.append("export")
    if support_bits.get("runtime"):
        parts.append("runtime")
    if addr.startswith("signals.") and isinstance((runtime or {}).get("signals"), dict):
        if addr.split(".", 1)[1] in (runtime or {}).get("signals", {}):
            parts.append("runtime-signal")
    evidence = ", ".join(parts) if parts else "none"
    if status == "OPEN":
        confidence = "direct" if source not in ("default", "missing") and meta else "partial"
    elif status == "SPLIT":
        confidence = "partial" if parts else "low"
    else:
        confidence = "direct" if not meta or source in ("missing",) else "low"
    if source == "default" and status == "OPEN":
        confidence = "direct"
    elif source == "default" and status != "CLOSED":
        confidence = "inferred"
    return evidence, confidence

def _recommended_probe(addr: str, scope: str, status: str, blocker: str, confidence: str) -> str:
    blocker_l = str(blocker or '').lower()
    if addr.startswith("project.surface."):
        return "Surface / Mapping Inspector"
    if "preview/export" in blocker_l or "preview/export parity" in blocker_l:
        return "Preview / Export Parity"
    if addr.startswith("layers["):
        if "opacity" in addr or "enabled" in addr or "blend_mode" in addr or "order" in addr:
            return "Layer Field Probe"
        return "Layer Wiring Inspector"
    if addr.startswith("project.variables.") or addr.startswith("signals.") or addr.startswith("systems.") or addr.startswith("project.spatial."):
        return "Resolver Inspector"
    if status == "CLOSED" and "registry" in blocker_l:
        return "Canonical Address Registry"
    if scope in ("project_postfx", "operator_param"):
        return "Resolver Inspector"
    return "Triage Report"

def _debt_reason(addr: str, status: str, source: str, support_bits: Dict[str, bool], writable: bool, blocker: str, confidence: str) -> str:
    blocker_l = str(blocker or '').lower()
    if 'preview/export parity split' in blocker_l:
        return 'preview_export_split'
    if 'runtime-only' in blocker_l:
        return 'runtime_only_unproven' if status == 'SPLIT' else 'runtime_only'
    if 'registry missing' in blocker_l:
        return 'registry_missing'
    if 'fell back to default' in blocker_l:
        return 'resolver_default_fallback'
    if 'canonical default' in blocker_l and status == 'OPEN':
        return 'canonical_default_open'
    if status == 'CLOSED' and not writable:
        return 'read_only_unresolved'
    if support_bits.get('authored') and not any(support_bits.get(k) for k in ('preview','export')):
        return 'unwritten_authored_path'
    if confidence in ('low','inferred','partial'):
        return 'low_confidence_inferred_support'
    return 'needs_probe'

def _address_triage_rows(project: Dict[str, Any], runtime: Optional[Dict[str, Any]] = None) -> List[Tuple[str, ...]]:
    reg = canonical_registry() if callable(canonical_registry) else canonical_registry
    rows: List[Tuple[str, ...]] = []
    for addr in _iter_triage_addresses(project, runtime):
        templ = _templated_registry_key(addr)
        meta = reg.get(templ) or {}
        if not meta:
            probe = _recommended_probe(addr, "unknown", "CLOSED", "registry missing", "direct")
            reason = 'registry_missing'
            rows.append((addr, "CLOSED", "missing", "unknown", "none", "no", "no", "no", "no", "no", "registry missing", "none", "direct", reason, probe))
            continue
        scope = str(meta.get("scope") or "")
        writable = bool(meta.get("writable", True))
        res = resolve_address(project=project, address=addr, runtime=runtime, default=None)
        source = str(getattr(res, "source", "default") or "default")
        probe_store = (((project.get("ui") if isinstance(project, dict) else {}) or {}).get("triage_probe_results") or {})
        probe_payload = probe_store.get(addr) if isinstance(probe_store, dict) else None
        probe_result = str((probe_payload or {}).get("result") or "").strip().lower() if isinstance(probe_payload, dict) else ""
        support_bits = _support_map(scope)
        support = _support_matrix_text(support_bits)
        writable_txt = 'yes' if writable else 'no'
        authored_txt = 'yes' if support_bits.get('authored') else 'no'
        preview_txt = 'yes' if support_bits.get('preview') else 'no'
        export_txt = 'yes' if support_bits.get('export') else 'no'
        runtime_txt = 'yes' if support_bits.get('runtime') else 'no'
        status = "OPEN"
        blocker = "none"
        if source == "default":
            status = "OPEN"
            blocker = "canonical default"
        elif source == "missing":
            status = "CLOSED"
            blocker = "resolver missing value"
        elif source == "runtime" and not (support_bits.get("preview") and support_bits.get("export")):
            status = "SPLIT"
            blocker = "runtime value without full preview/export parity"
        elif support_bits.get("preview") != support_bits.get("export"):
            status = "SPLIT"
            blocker = "preview/export parity split"
        elif support_bits.get("authored") and source == "runtime":
            status = "SPLIT"
            blocker = "runtime-only source; verify authored parity"

        if probe_result in ("open", "pass", "proved", "ok", "skipped"):
            status = "OPEN"
            blocker = "none"
        elif probe_result in ("split", "fail", "missing", "closed", "mismatch"):
            status = "SPLIT" if probe_result != "missing" else "CLOSED"
            blocker = str((probe_payload or {}).get("note") or blocker or "probe reported blocker")
        evidence, confidence = _address_evidence_and_confidence(addr, meta, source, support_bits, status, runtime)
        reason = _debt_reason(addr, status, source, support_bits, writable, blocker, confidence)
        probe = _recommended_probe(addr, scope, status, blocker, confidence)
        rows.append((addr, status, source, scope, support, authored_txt, preview_txt, export_txt, runtime_txt, writable_txt, blocker, evidence, confidence, reason, probe))
    return rows

TRIAGE_ACTIONS: Dict[str, Dict[str, str]] = {
    "canonical_resolver": {
        "SPLIT": "Inspect the first unresolved canonical address in Resolver Inspector and remove the direct/raw fallback path.",
        "CLOSED": "Restore missing registry coverage or resolver wiring before relying on higher-level tooling.",
    },
    "surface_mapping": {
        "SPLIT": "Use canonical surface snapshot + mapping inspector to remove any remaining raw layout compatibility path.",
        "CLOSED": "Fix canonical surface truth first: shape/count/width/height/mapping must resolve cleanly.",
    },
    "composition": {
        "SPLIT": "Trace the first failing layer field through resolve_address and delete the split write/read path instead of adding aliases.",
        "CLOSED": "Restore canonical layer composition fields before preview/export triage continues.",
    },
    "preview_export_parity": {
        "SPLIT": "Run the parity probe evidence and fix the first mismatch between preview and export canonical reads.",
        "CLOSED": "Do not proceed until preview/export parity produces a usable canonical result.",
    },
    "runtime_domains": {
        "SPLIT": "Inspect the first runtime variable/signal/system address that resolves to default and wire it into the canonical runtime truth surface.",
        "CLOSED": "Restore runtime-domain resolver wiring before expanding gates or higher-level systems.",
    },
    "project_validation": {
        "SPLIT": "Clear the first empty structural issue so validation stops masking deeper triage signals.",
        "CLOSED": "Fix invalid/dangling structural issues before any higher-level diagnosis or era work.",
    },
}

def _status_rank(s: Status) -> int:
    return {"OPEN": 0, "SPLIT": 1, "CLOSED": 2}.get(str(s or "").upper(), 2)

def _merge_status(a: Status, b: Status) -> Status:
    return a if _status_rank(a) >= _status_rank(b) else b

def _bool_status(ok: bool, closed_msg: Optional[str] = None) -> Tuple[Status, str]:
    if ok:
        return "OPEN", "ok"
    return ("CLOSED" if closed_msg else "SPLIT"), (closed_msg or "needs attention")

def _legacy_layer_mirrors(project: Dict[str, Any]) -> List[str]:
    hits: List[str] = []
    layers = project.get("layers") or []
    for i, layer in enumerate(layers):
        if not isinstance(layer, dict):
            continue
        params = layer.get("params") or {}
        if not isinstance(params, dict):
            continue
        for key in ("layer_opacity", "layer_enabled", "layer_blend_mode", "layer_order"):
            if key in params:
                hits.append(f"layers[{i}].params.{key}")
    return hits

def _resolver_presence(project: Dict[str, Any], runtime: Optional[Dict[str, Any]] = None) -> Tuple[Status, str]:
    reg = canonical_registry() if callable(canonical_registry) else canonical_registry
    if callable(runtime):
        runtime = runtime()
    layers = project.get("layers") or []
    addrs = [
        "project.surface.kind",
        "project.surface.count",
        "project.surface.width",
        "project.surface.height",
        "project.surface.mapping.serpentine",
        "project.postfx.trail_amount",
    ]
    if layers:
        addrs.extend([
            "layers[0].opacity",
            "layers[0].enabled",
            "layers[0].blend_mode",
            "layers[0].order",
            "layers[0]._op_overrides.gain",
        ])
    missing: List[str] = []
    unresolved: List[str] = []
    for addr in addrs:
        templ = addr
        if addr.startswith("layers["):
            templ = addr.replace("[0]", "[*]", 1)
        if templ not in reg:
            missing.append(addr)
            continue
        res = resolve_address(project=project, address=addr, runtime=runtime, default=None)
        source = str(getattr(res, "source", "default") or "default")
        probe_store = (((project.get("ui") if isinstance(project, dict) else {}) or {}).get("triage_probe_results") or {})
        probe_payload = probe_store.get(addr) if isinstance(probe_store, dict) else None
        probe_result = str((probe_payload or {}).get("result") or "").strip().lower() if isinstance(probe_payload, dict) else ""
        # Canonical defaults are valid resolver truth when the address is
        # registered and there is no conflicting debt elsewhere. Only treat
        # genuinely missing resolver values as unresolved here.
        if source == "missing":
            unresolved.append(addr)
    if missing:
        return "CLOSED", f"registry missing: {', '.join(missing[:6])}"
    if unresolved:
        return "SPLIT", f"resolver missing: {', '.join(unresolved[:6])}"
    return "OPEN", "registry present and core addresses resolve canonically (including canonical defaults)"

def _surface_status(project: Dict[str, Any]) -> Tuple[Status, str]:
    spec = get_surface_spec(project)
    if not spec:
        return "CLOSED", "SurfaceSpec missing"
    if spec.kind == "strip":
        if int(getattr(spec, "count", 0) or 0) <= 0:
            return "CLOSED", "strip count invalid"
    elif spec.kind == "cells":
        if int(getattr(spec, "width", 0) or 0) <= 0 or int(getattr(spec, "height", 0) or 0) <= 0:
            return "CLOSED", "cells width/height invalid"
    else:
        return "SPLIT", f"unexpected kind={getattr(spec, 'kind', None)!r}"
    return "OPEN", f"SurfaceSpec kind={spec.kind} count={spec.count} {spec.width}x{spec.height}"

def _composition_status(project: Dict[str, Any], runtime: Optional[Dict[str, Any]] = None) -> Tuple[Status, str]:
    layers = project.get("layers") or []
    if not layers:
        return "OPEN", "no layers authored yet"
    mirrors = _legacy_layer_mirrors(project)
    if mirrors:
        return "SPLIT", f"legacy mirror residue: {', '.join(mirrors[:6])}"
    bad: List[str] = []
    for i, _layer in enumerate(layers):
        for field in ("opacity", "enabled", "blend_mode", "order"):
            addr = f"layers[{i}].{field}"
            res = resolve_address(project=project, address=addr, runtime=runtime, default=None)
            if getattr(res, "source", "default") == "default":
                if field == "order":
                    # Canonical default layer ordering is acceptable when no authored
                    # order exists and no mirror/split residue is present.
                    continue
                bad.append(addr)
    if bad:
        return "SPLIT", f"resolver default on: {', '.join(bad[:6])}"
    return "OPEN", "layer composition resolves canonically"

def _parity_status(project: Dict[str, Any]) -> Tuple[Status, str]:
    report = preview_export_parity_probe(project)
    text = "\n".join(report if isinstance(report, list) else [str(report)])
    if "Status: FAIL" in text or "aborted" in text.lower() or "missing" in text.lower():
        return "CLOSED", text.splitlines()[-1] if text.splitlines() else "parity failed"
    if "Status: PASS" in text:
        return "OPEN", "preview/export parity probe passes"
    return "SPLIT", "parity probe inconclusive"

def _runtime_domains_status(project: Dict[str, Any], runtime: Optional[Dict[str, Any]] = None) -> Tuple[Status, str]:
    notes: List[str] = []
    status: Status = "OPEN"
    vars_dict = project.get("variables") or {}
    if isinstance(vars_dict, dict):
        num = vars_dict.get("number") or {}
        tog = vars_dict.get("toggle") or {}
        if isinstance(num, dict):
            for name in sorted(num.keys())[:3]:
                res = resolve_address(project=project, address=f"project.variables.number.{name}", runtime=runtime, default=None)
                if getattr(res, "source", "default") == "default":
                    status = _merge_status(status, "SPLIT")
                    notes.append(f"var:number.{name}")
        if isinstance(tog, dict):
            for name in sorted(tog.keys())[:3]:
                res = resolve_address(project=project, address=f"project.variables.toggle.{name}", runtime=runtime, default=None)
                if getattr(res, "source", "default") == "default":
                    status = _merge_status(status, "SPLIT")
                    notes.append(f"var:toggle.{name}")
    sigs = (runtime or {}).get("signals") or {}
    if isinstance(sigs, dict) and sigs:
        key = sorted(sigs.keys())[0]
        res = resolve_address(project=project, address=f"signals.{key}", runtime=runtime, default=None)
        if getattr(res, "source", "default") == "default":
            status = _merge_status(status, "SPLIT")
            notes.append(f"signal:{key}")
    return status, ("runtime domains resolve canonically" if not notes else f"check: {', '.join(notes[:6])}")

def _validation_status(project: Dict[str, Any]) -> Tuple[Status, str]:
    d = diagnose_project(project)
    invalid = list(d.get("invalid") or [])
    dangling = list(d.get("dangling") or [])
    empty = list(d.get("empty") or [])
    if invalid or dangling:
        sample = (invalid + dangling)[:4]
        return "CLOSED", "; ".join(sample)
    if empty:
        return "SPLIT", "; ".join(empty[:4])
    return "OPEN", "no invalid/dangling/empty structural issues"

def build_triage_rows(project: Dict[str, Any], runtime: Optional[Dict[str, Any]] = None) -> List[Tuple[str, Status, str]]:
    rows: List[Tuple[str, Status, str]] = []
    rows.append(("canonical_resolver",) + _resolver_presence(project, runtime))
    rows.append(("surface_mapping",) + _surface_status(project))
    rows.append(("composition",) + _composition_status(project, runtime))
    rows.append(("preview_export_parity",) + _parity_status(project))
    rows.append(("runtime_domains",) + _runtime_domains_status(project, runtime))
    rows.append(("project_validation",) + _validation_status(project))
    return rows

def first_non_open_domain(rows: Iterable[Tuple[str, Status, str]]) -> Optional[Tuple[str, Status, str]]:
    for row in rows:
        if str(row[1]).upper() != "OPEN":
            return row
    return None

def first_non_open_address(project: Dict[str, Any], runtime: Optional[Dict[str, Any]] = None) -> Optional[Tuple[str, ...]]:
    for row in _address_triage_rows(project, runtime):
        if str(row[1]).upper() != "OPEN":
            return row
    return None



def _support_matrix(scope: str) -> Dict[str, bool]:
    """Compatibility wrapper for older callers still using matrix wording."""
    return _support_map(scope)


__all__ = [name for name in globals() if ((name.startswith("_") and not name.startswith("__")) or name in {"Status", "TRIAGE_ADDRESS_MATRIX", "build_triage_rows", "first_non_open_domain", "first_non_open_address", "render_triage_report"})]
