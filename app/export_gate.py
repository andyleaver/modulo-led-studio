"""Export gating helpers.

Goal: never let users think something is exportable when it isn't.
Used by Presets/Playlist UI and exporter preflight.

This module is intentionally lightweight and relies on export.export_eligibility
as the single shipped eligibility table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

@dataclass(frozen=True)
class ExportIssue:
    layer_index: int
    layer_name: str
    behavior: str
    status: str
    reason: str

def _layer_name(L: Dict[str, Any], idx: int) -> str:
    try:
        nm = str(L.get("name") or "").strip()
        return nm or f"Layer {idx}"
    except Exception:
        return f"Layer {idx}"

def analyze_project_export_issues(project: Dict[str, Any], *, target_id: Optional[str] = None) -> List[ExportIssue]:
    """Return a list of export issues for this project.

    target_id is accepted for future per-target rules; currently the shipped
    eligibility table is global.

    Additional dynamic rules enforced here:
    - Kernel/write_the_loop requires a non-empty C++ body (params['cpp']).
    """
    try:
        from export.export_eligibility import get_eligibility, ExportStatus
    except Exception:
        # If eligibility module is unavailable, be conservative.
        return [ExportIssue(-1, "(project)", "(unknown)", "blocked", "Eligibility table unavailable")]

    out: List[ExportIssue] = []
    layers = project.get("layers") if isinstance(project, dict) else None
    if not isinstance(layers, list):
        return out

    for i, L0 in enumerate(layers):
        if not isinstance(L0, dict):
            continue
        L = L0
        beh = str(L.get("behavior") or "").strip()
        kind = str(L.get("kind") or "").strip().lower()
        nm = _layer_name(L, i)

        # Dynamic kernel rule: require cpp body for export.
        if (kind == "kernel") or (beh in ("kernel","write_the_loop")):
            params = L.get("params") if isinstance(L.get("params"), dict) else {}
            cpp = str(params.get("cpp") or "").strip()
            if not cpp:
                out.append(ExportIssue(i, nm, beh or "kernel", "blocked", "Kernel layer requires C++ export body (params.cpp)"))
                continue

        el = get_eligibility(beh)
        if getattr(el, "status", None) != ExportStatus.EXPORTABLE:
            out.append(ExportIssue(i, nm, beh, str(el.status), str(getattr(el, "reason", "") or "")))

    return out

def format_export_issues(issues: List[ExportIssue]) -> str:
    if not issues:
        return ""
    lines = ["This project contains layers that are not exportable:"]
    for it in issues[:30]:
        loc = f"L{it.layer_index}" if it.layer_index >= 0 else "(project)"
        nm = it.layer_name
        beh = it.behavior
        reason = it.reason or it.status
        lines.append(f"- {loc} '{nm}': {beh} → {it.status} — {reason}")
    if len(issues) > 30:
        lines.append(f"…and {len(issues) - 30} more")
    return "\n".join(lines)

def log_export_issues_diag(issues: List[ExportIssue], *, where: str, target_id: Optional[str] = None) -> None:
    """Best-effort diagnostics logging."""
    if not issues:
        return
    try:
        from runtime.diagnostics import GLOBAL_DIAGS
        GLOBAL_DIAGS.message(
            domain="EXPORT",
            code="EXPORT_GATING_WARN",
            summary=f"Export gating warning from {where}",
            details={
                "where": where,
                "target_id": target_id,
                "issues": [it.__dict__ for it in issues],
            },
        )
    except Exception:
        return
