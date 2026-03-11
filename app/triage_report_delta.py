from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.project_diagnostics import diagnose_project, layer_wiring_inspector, preview_export_parity_probe, surface_mapping_inspector
from app.project_model import get_surface_kind, get_surface_spec
from app.app_identity import APP_ID
from runtime.canonical_addr import canonical_registry
from runtime.resolver import resolve_address


def _snapshot_from_rows(rows: List[Tuple[str, ...]]) -> Dict[str, Tuple[str, str, str]]:
    return {row[0]: (str(row[1]), str(row[12]), str(row[10] or '')) for row in rows}


def _load_probe_results(project: Dict[str, Any]) -> Dict[str, Any]:
    ui = (project.get('ui') or {}) if isinstance(project, dict) else {}
    stored = dict(ui.get('triage_probe_results') or {}) if isinstance(ui, dict) else {}
    results: Dict[str, Any] = {
        'health': {'probe': 'health', 'result': 'ok' if diagnose_project(project) else 'empty'},
        'wiring': {'probe': 'wiring', 'result': 'ok' if layer_wiring_inspector(project) else 'empty'},
        'parity': {'probe': 'parity', 'result': 'ok' if preview_export_parity_probe(project) else 'empty'},
        'surface': {'probe': 'surface', 'result': 'ok' if surface_mapping_inspector(project) else 'empty'},
    }
    for key, payload in stored.items():
        if isinstance(payload, dict):
            results[str(key)] = dict(payload)
        else:
            results[str(key)] = {'probe': str(key), 'result': str(payload)}
    return results


def _apply_probe_results(project: Dict[str, Any], rows: List[Tuple[str, ...]]) -> Dict[str, Any]:
    results = _load_probe_results(project)
    spec = get_surface_spec(project)
    return {
        'project_id': APP_ID,
        'surface_kind': getattr(spec, 'kind', None) if spec else None,
        'row_count': len(rows),
        'registry_size': len(canonical_registry() or {}),
        'results': results,
    }


def _probe_result_summary(results: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key, value in (results or {}).items():
        if isinstance(value, dict):
            out[str(key)] = str(value.get('result') or ('ok' if value else 'empty'))
        else:
            out[str(key)] = 'ok' if value else 'empty'
    return out


def _triage_delta(previous: Dict[str, Any] | None, rows: List[Tuple[str, ...]]) -> Dict[str, Any]:
    prev = dict(previous or {})
    current = _snapshot_from_rows(rows)
    old = dict(prev.get('snapshot') or {})
    new_addrs = sorted(set(current) - set(old))
    removed = sorted(set(old) - set(current))
    changed = sorted(addr for addr in set(current) & set(old) if current[addr] != old[addr])
    regressions = []
    improvements = []
    for addr in changed:
        old_status, _old_conf, _old_blocker = old[addr]
        new_status, _new_conf, _new_blocker = current[addr]
        if old_status == 'CLOSED' and new_status != 'CLOSED':
            regressions.append(addr)
        elif old_status != 'CLOSED' and new_status == 'CLOSED':
            improvements.append(addr)
    return {
        'new_addresses': new_addrs,
        'removed_addresses': removed,
        'changed_addresses': changed,
        'regressions': regressions,
        'improvements': improvements,
        'snapshot': current,
    }


def _store_triage_baseline(project: Dict[str, Any], rows: List[Tuple[str, ...]]) -> Dict[str, Any]:
    baseline = {
        'snapshot': _snapshot_from_rows(rows),
        'surface_kind': get_surface_kind(project),
    }
    project.setdefault('_triage', {})['baseline'] = baseline
    return baseline


def _store_execution_pack(project: Dict[str, Any], pack: Dict[str, Any]) -> None:
    project.setdefault('_triage', {})['execution_pack'] = dict(pack or {})


def _previous_execution_pack(project: Dict[str, Any]) -> Dict[str, Any] | None:
    triage = project.get('_triage') or {}
    pack = triage.get('execution_pack')
    return dict(pack) if isinstance(pack, dict) else None


def _closure_basis_map(rows: List[Tuple[str, ...]]) -> Dict[str, Tuple[str, str, str]]:
    return {row[0]: (str(row[1]), str(row[12]), str(row[10] or '')) for row in rows}


def _store_closure_basis_map(project: Dict[str, Any], rows: List[Tuple[str, ...]]) -> Dict[str, Tuple[str, str, str]]:
    basis = _closure_basis_map(rows)
    project.setdefault('_triage', {})['closure_basis'] = basis
    return basis


def _stability_summary(current_rows: List[Tuple[str, ...]], baseline: Dict[str, Any] | None, execution_pack: Dict[str, Any] | None) -> Dict[str, Any]:
    delta = _triage_delta(baseline, current_rows)
    snapshot = _snapshot_from_rows(current_rows)
    prev_pack = dict(execution_pack or {})
    prev_snapshot = dict(prev_pack.get('snapshot') or {})
    stable = sorted(addr for addr in set(snapshot) & set(prev_snapshot) if snapshot[addr] == prev_snapshot[addr])
    return {
        'stable_count': len(stable),
        'changed_count': len(delta.get('changed_addresses') or []),
        'regression_count': len(delta.get('regressions') or []),
        'improvement_count': len(delta.get('improvements') or []),
        'delta': delta,
    }


__all__ = [name for name in globals() if ((name.startswith("_") and not name.startswith("__")) or name in {"Status", "TRIAGE_ADDRESS_MATRIX", "build_triage_rows", "first_non_open_domain", "first_non_open_address", "render_triage_report"})]
