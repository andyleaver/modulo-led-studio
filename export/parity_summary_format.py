from __future__ import annotations

from typing import Any, Dict

from app.project_model import get_surface_spec
from core.surface_compat import get_surface_mapping_values
from export.export_eligibility import ExportStatus

from .parity_summary_core import build_parity_summary


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
    counts = {
        ExportStatus.EXPORTABLE: 0,
        ExportStatus.BLOCKED: 0,
        ExportStatus.PREVIEW_ONLY: 0,
    }
    try:
        for ent in (ps.get("layers") or []):
            st = str(ent.get("status") or "").strip()
            if st in counts:
                counts[st] += 1
    except Exception as e:
        from runtime.diagnostics import GLOBAL_DIAGS

        GLOBAL_DIAGS.exception(
            e,
            domain="EXPORT",
            code="SWALLOWED_EXCEPTION",
            summary="swallowed exception",
            details={"file": "export/parity_summary_format.py"},
        )
    return counts


def format_project_badge(ps: Dict[str, Any]) -> str:
    return "PASS" if bool(ps.get("ok")) else "BLOCKED"


def format_export_report_line(ps: Dict[str, Any]) -> str:
    st = format_project_badge(ps)
    c = summarize_layers(ps)
    return (
        f"{st}  (exportable={c.get(ExportStatus.EXPORTABLE, 0)} "
        f"blocked={c.get(ExportStatus.BLOCKED, 0)} "
        f"preview={c.get(ExportStatus.PREVIEW_ONLY, 0)})"
    )


def format_export_block_message(ps: Dict[str, Any]) -> str:
    if bool(ps.get("ok")):
        return ""
    errs = ps.get("errors") or []
    if not errs:
        return "Export blocked."
    return "Export blocked: " + str(errs[0])


def _surface_geometry(project: Dict[str, Any]) -> Dict[str, Any]:
    spec = get_surface_spec(project)
    if not spec:
        raise RuntimeError("SurfaceSpec missing — export blocked.")
    mapping = get_surface_mapping_values(spec)
    return {
        "kind": spec.kind,
        "width": spec.width,
        "height": spec.height,
        "count": spec.count,
        "mapping": mapping,
        "serpentine": bool(mapping.get("serpentine", False)),
        "flip_x": bool(mapping.get("flip_x", False)),
        "flip_y": bool(mapping.get("flip_y", False)),
        "rotate": int(mapping.get("rotate", 0)),
        "origin": str(mapping.get("origin", "top_left")),
    }


__all__ = [
    "build_parity_summary",
    "layer_parity",
    "layer_tag_text",
    "summarize_layers",
    "format_project_badge",
    "format_export_report_line",
    "format_export_block_message",
]
