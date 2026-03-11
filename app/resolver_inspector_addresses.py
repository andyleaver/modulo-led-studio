from typing import Any, Dict, Iterable, List

from runtime import canonical_addr


def sample_addresses_for_project(project: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    out.extend([
        'project.surface.kind',
        'project.surface.count',
        'project.surface.width',
        'project.surface.height',
        'project.surface.mapping.serpentine',
        'project.surface.mapping.flip_x',
        'project.surface.mapping.flip_y',
        'project.surface.mapping.rotate',
        'project.surface.mapping.origin',
        'project.ui.selected_layer',
        'project.audio.routes',
        'project.audio.preset_name',
    ])
    layers = project.get('layers') or []
    if isinstance(layers, list):
        for i, layer in enumerate(layers[:8]):
            if not isinstance(layer, dict):
                continue
            out.extend([
                f'layers[{i}].enabled',
                f'layers[{i}].opacity',
                f'layers[{i}].blend_mode',
                f'layers[{i}].order',
            ])
    return out


def entry_meta(address: str) -> Dict[str, Any]:
    meta = canonical_addr.describe(address) if hasattr(canonical_addr, 'describe') else None
    return meta if isinstance(meta, dict) else {}


def inspect_project_addresses(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{'address': address, 'meta': entry_meta(address)} for address in sample_addresses_for_project(project)]


def iter_runtime_variable_addresses(runtime_vars: Dict[str, Any]) -> Iterable[str]:
    for key in sorted((runtime_vars or {}).keys()):
        value = (runtime_vars or {}).get(key)
        if isinstance(value, bool):
            yield f'project.variables.toggle.{key}'
        else:
            yield f'project.variables.number.{key}'


def iter_signal_addresses(signal_bus: Dict[str, Any]) -> Iterable[str]:
    for key in sorted((signal_bus or {}).keys()):
        yield f'signals.{key}'


def iter_particle_system_addresses(project: Dict[str, Any]) -> Iterable[str]:
    systems = (project.get('particle_systems') or {}) if isinstance(project, dict) else {}
    if isinstance(systems, dict) and systems:
        yield 'systems.particles.total'
        for key in sorted(systems.keys()):
            yield f'systems.particles.{key}.count'
            yield f'systems.particles.{key}.max_particles'


def iter_spatial_addresses(project: Dict[str, Any]) -> Iterable[str]:
    # Surface/geometry inspector output must use canonical addresses so the
    # diagnostics layer is evaluating the same truth as resolver/preview/export.
    for address in (
        'project.surface.kind',
        'project.surface.count',
        'project.surface.width',
        'project.surface.height',
        'project.surface.mapping.serpentine',
        'project.surface.mapping.flip_x',
        'project.surface.mapping.flip_y',
        'project.surface.mapping.rotate',
        'project.surface.mapping.origin',
    ):
        yield address
