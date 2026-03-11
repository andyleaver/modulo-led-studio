from __future__ import annotations

from collections import OrderedDict
from typing import Dict, List, Tuple


def _proof_class_for_row(row: Tuple[str, ...]) -> str:
    status, source, authored, preview, export, runtime_txt, confidence = row[1], row[2], row[5], row[6], row[7], row[8], row[12]
    preview_b = preview == 'yes'
    export_b = export == 'yes'
    runtime_b = runtime_txt == 'yes'
    if status == 'OPEN' and preview_b and export_b:
        return 'direct_preview_export'
    if status == 'OPEN' and runtime_b and source == 'runtime' and confidence == 'direct':
        return 'direct_runtime'
    if confidence == 'direct' and source not in ('default', 'missing'):
        return 'direct_probe'
    if confidence in ('inferred', 'partial') or status == 'SPLIT':
        return 'inferred_only'
    return 'missing'


def _probe_outcome_hint(row: Tuple[str, ...]) -> str:
    addr = row[0]
    if addr.startswith('project.surface.'):
        return 'close when canonical SurfaceSpec validates and preview/export geometry match the same surface snapshot'
    if addr.startswith('layers['):
        return 'close when Resolver Inspector, Layer Wiring Inspector, and preview/export parity all agree on the same canonical layer field'
    if addr.startswith('project.postfx.'):
        return 'close when preview and export both apply the same canonical postfx field without fallback/default reads'
    if addr.startswith('project.variables.'):
        return 'close when authored value resolves canonically and runtime evidence matches without default fallback'
    if addr.startswith('signals.'):
        return 'close when runtime signal snapshot resolves directly and no inferred-only support remains'
    if addr.startswith('project.spatial.') or addr.startswith('systems.'):
        return 'close when runtime/system evidence is direct and canonical resolver reads no longer fall back to defaults'
    return 'close when the recommended probe yields direct canonical proof with no blocker-backed split'


def _count_by_status(rows: List[Tuple[str, ...]]) -> Dict[str, int]:
    counts: Dict[str, int] = OrderedDict((k, 0) for k in ('OPEN', 'SPLIT', 'CLOSED'))
    for row in rows:
        status = str(row[1]).upper()
        counts[status] = counts.get(status, 0) + 1
    return counts


def _count_by_confidence(rows: List[Tuple[str, ...]]) -> Dict[str, int]:
    counts: Dict[str, int] = OrderedDict()
    for row in rows:
        confidence = str(row[12]).strip().lower()
        counts[confidence] = counts.get(confidence, 0) + 1
    return counts


def _domain_confidence_counts(rows: List[Tuple[str, ...]]) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    for row in rows:
        domain = row[0]
        confidence = str(row[12]).strip().lower()
        bucket = out.setdefault(domain, {})
        bucket[confidence] = bucket.get(confidence, 0) + 1
    return out


__all__ = [name for name in globals() if ((name.startswith("_") and not name.startswith("__")) or name in {"Status", "TRIAGE_ADDRESS_MATRIX", "build_triage_rows", "first_non_open_domain", "first_non_open_address", "render_triage_report"})]
