from app.project_canonical import canonicalize_project_dict
from typing import Any, Dict, List

from .resolver_inspector_addresses import (
    inspect_project_addresses,
    iter_particle_system_addresses,
    iter_runtime_variable_addresses,
    iter_signal_addresses,
    iter_spatial_addresses,
)


def render_runtime_domains(project: Dict[str, Any], runtime_vars: Dict[str, Any] = None, signal_bus: Dict[str, Any] = None) -> str:
    project2, _ = canonicalize_project_dict(project or {})
    rows: List[str] = ['Runtime domains:']
    rows.append('  Variables:')
    rows.extend(f'    - {addr}' for addr in iter_runtime_variable_addresses(runtime_vars or {}))
    rows.append('  Signals:')
    rows.extend(f'    - {addr}' for addr in iter_signal_addresses(signal_bus or {}))
    rows.append('  Spatial:')
    rows.extend(f'    - {addr}' for addr in iter_spatial_addresses(project2))
    rows.append('  Systems:')
    rows.extend(f'    - {addr}' for addr in iter_particle_system_addresses(project2))
    return '\n'.join(rows)


def render_registry_report(project: Dict[str, Any]) -> str:
    project2, _ = canonicalize_project_dict(project or {})
    rows = ['Resolver registry report:']
    for entry in inspect_project_addresses(project2):
        rows.append(f"- {entry['address']}: {entry['meta']}")
    return '\n'.join(rows)


def render_resolver_inspector(project: Dict[str, Any]) -> str:
    project2, _ = canonicalize_project_dict(project or {})
    rows = ['Resolver inspector:']
    for entry in inspect_project_addresses(project2):
        rows.append(f"- {entry['address']}")
    return '\n'.join(rows)


def render_modulotor_report(project: Dict[str, Any]) -> str:
    project2, _ = canonicalize_project_dict(project or {})
    modulators = ((project2.get('modulators') or []) if isinstance(project2, dict) else [])
    rows = ['Modulator report:']
    if isinstance(modulators, list):
        for index, item in enumerate(modulators):
            if isinstance(item, dict):
                rows.append(f"- {index}: {item.get('target') or item.get('address') or ''}")
    return '\n'.join(rows)
