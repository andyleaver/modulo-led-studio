from __future__ import annotations

import json
from typing import Any

from app.project_canonical import canonicalize_project_dict
from .mapping_parity_core import (
    ParityMismatch,
    export_strip_index,
    run_project_mapping_parity_probe as _run_project_mapping_parity_probe,
)
from .mapping_parity_reports import (
    dump_surface_mapping as _dump_surface_mapping,
    run_project_mapping_parity_cases as _run_project_mapping_parity_cases,
    run_project_mapping_parity_cells as _run_project_mapping_parity_cells,
    run_project_mapping_parity_sweep as _run_project_mapping_parity_sweep,
    run_project_mapping_pattern_probe as _run_project_mapping_pattern_probe,
)


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=False)


def _format_mapping_report(title: str, report: dict) -> str:
    lines = [f"== {title} =="]
    lines.append(f"result: {'OK' if bool(report.get('ok')) else 'FAIL'}")
    lines.append(f"mode: {report.get('mode', 'n/a')}")
    lines.append(f"surface_kind: {report.get('kind', 'strip')}")
    lines.append(f"checked_points: {int(report.get('checked_points') or 0)}")
    mapping = report.get('mapping') if isinstance(report.get('mapping'), dict) else {}
    lines.append('mapping: ' + _json(mapping))
    mismatches = report.get('mismatches') if isinstance(report.get('mismatches'), list) else []
    lines.append(f"mismatch_count: {len(mismatches)}")
    if mismatches:
        lines.append('sample_mismatches:')
        for item in mismatches[:24]:
            lines.append('  ' + _json(item))
        if len(mismatches) > 24:
            lines.append(f"  ... {len(mismatches) - 24} more")
    return "\n".join(lines)


def _format_mapping_cases(title: str, report: dict) -> str:
    lines = [f"== {title} =="]
    cases = report.get('cases') if isinstance(report.get('cases'), list) else []
    lines.append(f"case_count: {len(cases)}")
    for idx, item in enumerate(cases, start=1):
        case = item.get('case') if isinstance(item, dict) else {}
        rep = item.get('report') if isinstance(item, dict) else {}
        lines.append(f"[{idx}] kind={case.get('kind')} ok={bool(rep.get('ok'))} mismatches={len(rep.get('mismatches') or [])}")
        lines.append('  case: ' + _json(case))
        mapping = rep.get('mapping') if isinstance(rep.get('mapping'), dict) else {}
        lines.append('  mapping: ' + _json(mapping))
    return "\n".join(lines)


def _format_mapping_points(title: str, report: dict) -> str:
    lines = [f"== {title} =="]
    lines.append('surface: ' + _json(report.get('surface') or {}))
    points = report.get('points') if isinstance(report.get('points'), list) else []
    lines.append(f"point_count: {len(points)}")
    for item in points[:80]:
        lines.append('  ' + _json(item))
    if len(points) > 80:
        lines.append(f"  ... {len(points) - 80} more")
    return "\n".join(lines)


def dump_surface_mapping(project):
    project2, _ = canonicalize_project_dict(project or {})
    return _json(_dump_surface_mapping(project2))


def run_project_mapping_parity_probe(project, mode='full'):
    project2, _ = canonicalize_project_dict(project or {})
    return _format_mapping_report('Surface/Mapping Parity', _run_project_mapping_parity_probe(project2, mode=mode))


def run_mapping_parity_probe(project, mode='full'):
    return run_project_mapping_parity_probe(project, mode=mode)


def run_mapping_pattern_probe(project):
    project2, _ = canonicalize_project_dict(project or {})
    return _format_mapping_points('Mapping Pattern Probe', _run_project_mapping_pattern_probe(project2))


def run_mapping_parity_sweep(project):
    project2, _ = canonicalize_project_dict(project or {})
    return _format_mapping_cases('Mapping Parity Sweep', _run_project_mapping_parity_sweep(project2))


def run_mapping_parity_cases(project):
    project2, _ = canonicalize_project_dict(project or {})
    return _format_mapping_cases('Mapping Parity Cases', _run_project_mapping_parity_sweep(project2))


def run_mapping_parity_cells(project):
    """Compatibility wrapper for older callers."""
    return run_mapping_parity_cases(project)


def run_mapping_parity_matrix(project):
    """Compatibility wrapper for older callers."""
    return run_mapping_parity_cases(project)
