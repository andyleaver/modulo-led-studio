"""Canonical address registry + parser (strict runtime).

Doctrine (March 2026):
- One canonical schema.
- One execution/mutation path.
- NO legacy runtime aliases/mirrors. Legacy is allowed ONLY as one-time migration on load.

This module therefore:
- Accepts ONLY canonical addresses at runtime.
- Keeps a small non-indexed canonicalization helper for Rules/UI that already
  operate in a known scope (e.g. "opacity" when the layer index is known
  separately).

Expand the registry as doors are opened.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

@dataclass(frozen=True)
class CanonicalTarget:
    # scope: 'layer_field' | 'project_postfx' | 'operator_param' | 'project_layout' | 'project_spatial' | 'project_variable' | 'project_ui' | 'project_audio' | 'signal' | 'system_state'
    scope: str
    key: str

@dataclass(frozen=True)
class ParsedAddress:
    """Fully parsed canonical address.

    scope:
      - layer_field      -> layers[index].<key>
      - project_postfx   -> project.postfx.<key>
      - operator_param   -> layers[index]._op_overrides.<key>
      - project_layout   -> project.surface.<...> / mapping
      - project_spatial  -> project.spatial.<...>
      - project_variable -> project.variables.number.<name> / toggle.<name>
      - project_ui       -> project.ui.selected_layer / project.ui.era_id
      - project_audio    -> project.audio.routes / project.audio.preset_name
      - signal           -> signals.<signal_key>
      - system_state     -> systems.<...> (read-only runtime/serialized system summaries)
    """
    scope: str
    key: str
    layer_index: Optional[int] = None
    address: str = ""
    # Always False in strict runtime.
    was_alias: bool = False

ALLOWED_BLEND_MODES = {"over", "add", "max", "multiply", "screen"}

# ---- Rules/UI helper canonicalization (NON-INDEXED, STRICT) ---------------
# These are canonical *targets* used when scope is already known.
# Runtime-address canonical form remains layers[i].<field>; these helpers are
# only for scoped callers such as Rules/UI bridges that already know layer i.
_CANON_LAYER_FIELDS = {
    "opacity": "opacity",
    "enabled": "enabled",
    "blend_mode": "blend_mode",
    "order": "order",
}

_CANON_POSTFX_FIELDS = {"trail_amount", "bleed_amount", "bleed_radius"}

_CANON_OPERATOR_FIELDS = {"gain", "gamma", "posterize_levels"}

def canonicalize_address(name: str) -> Optional[CanonicalTarget]:
    """Strict canonicalization of a destination name into a target scope + key.

    Returns:
      - CanonicalTarget for known non-effect destinations.
      - None for unknown destinations (treat as effect/layer param).
    """
    if not isinstance(name, str):
        return None
    raw = name.strip().lower()
    if not raw:
        return None

    # Layer fields (non-indexed canonical targets)
    if raw in _CANON_LAYER_FIELDS:
        return CanonicalTarget(scope="layer_field", key=_CANON_LAYER_FIELDS[raw])

    # Project PostFX (strict canonical keys)
    if raw.startswith("project.postfx."):
        tail = raw.split("project.postfx.", 1)[-1].strip()
        if tail in _CANON_POSTFX_FIELDS:
            return CanonicalTarget(scope="project_postfx", key=tail)

    # Operators (strict canonical targets)
    if raw.startswith("operator."):
        tail = raw.split("operator.", 1)[-1].strip()
        if tail in _CANON_OPERATOR_FIELDS:
            return CanonicalTarget(scope="operator_param", key=tail)

    return None


def canonicalize_layer_param_name(name: str) -> Optional[CanonicalTarget]:
    return canonicalize_address(name)

# ---- Registry / parser ----------------------------------------------------
_CANON_RE_LAYER_BRACKET = re.compile(r"^layers\[(\d+)\]\.([a-zA-Z_][a-zA-Z0-9_]*)$")

CANONICAL_ADDRESS_REGISTRY = {
    "layers[*].enabled": {"scope": "layer_field", "type": "bool"},
    "layers[*].opacity": {"scope": "layer_field", "type": "float01"},
    "layers[*].blend_mode": {"scope": "layer_field", "type": "enum", "values": sorted(ALLOWED_BLEND_MODES)},
    "layers[*].order": {"scope": "layer_field", "type": "int"},

    "project.postfx.trail_amount": {"scope": "project_postfx", "type": "float"},
    "project.postfx.bleed_amount": {"scope": "project_postfx", "type": "float"},
    "project.postfx.bleed_radius": {"scope": "project_postfx", "type": "float"},

    "layers[*]._op_overrides.gain": {"scope": "operator_param", "type": "float"},
    "layers[*]._op_overrides.gamma": {"scope": "operator_param", "type": "float"},
    "layers[*]._op_overrides.posterize_levels": {"scope": "operator_param", "type": "float"},

    "project.surface.kind": {"scope": "project_layout", "type": "enum", "values": ["strip", "cells"]},
    "project.surface.count": {"scope": "project_layout", "type": "int"},
    "project.surface.width": {"scope": "project_layout", "type": "int"},
    "project.surface.height": {"scope": "project_layout", "type": "int"},
    "project.surface.mapping.serpentine": {"scope": "project_layout", "type": "bool"},
    "project.surface.mapping.flip_x": {"scope": "project_layout", "type": "bool"},
    "project.surface.mapping.flip_y": {"scope": "project_layout", "type": "bool"},
    "project.surface.mapping.rotate": {"scope": "project_layout", "type": "enum", "values": [0, 90, 180, 270]},
    "project.surface.mapping.origin": {"scope": "project_layout", "type": "enum", "values": ["top_left", "top_right", "bottom_left", "bottom_right"]},

    "project.spatial.enabled": {"scope": "project_spatial", "type": "bool"},
    "project.spatial.world_scale": {"scope": "project_spatial", "type": "float"},
    "project.spatial.origin_x": {"scope": "project_spatial", "type": "float"},
    "project.spatial.origin_y": {"scope": "project_spatial", "type": "float"},
    "project.spatial.rotation_deg": {"scope": "project_spatial", "type": "float"},
    "project.spatial.mirror_x": {"scope": "project_spatial", "type": "bool"},
    "project.spatial.mirror_y": {"scope": "project_spatial", "type": "bool"},
    "project.spatial.use_layout_coords": {"scope": "project_spatial", "type": "bool"},

    "project.variables.number.*": {"scope": "project_variable", "type": "float", "notes": "Dynamic number variable names"},
    "project.variables.toggle.*": {"scope": "project_variable", "type": "bool", "notes": "Dynamic toggle variable names"},

    "project.ui.selected_layer": {"scope": "project_ui", "type": "int"},
    "project.ui.era_id": {"scope": "project_ui", "type": "string"},
    "project.ui.target_mask": {"scope": "project_ui", "type": "string", "nullable": True},

    "project.audio.routes": {"scope": "project_audio", "type": "json"},
    "project.audio.preset_name": {"scope": "project_audio", "type": "string"},

    "signals.*": {"scope": "signal", "type": "number", "notes": "Dynamic runtime signal keys from the signal registry / signal bus", "writable": False},
    "systems.particles.total": {"scope": "system_state", "type": "int", "writable": False, "notes": "Total serialized particles across particle_systems"},
    "systems.particles.*.count": {"scope": "system_state", "type": "int", "writable": False, "notes": "Serialized particle count for a named particle system"},
    "systems.particles.*.max_particles": {"scope": "system_state", "type": "int", "writable": False, "notes": "Configured max_particles for a named particle system"},
}

def parse_canonical_address(name: str) -> Optional[ParsedAddress]:
    """Parse ONLY canonical addresses (strict)."""
    if not isinstance(name, str):
        return None
    raw = name.strip()
    if not raw:
        return None
    n = raw.lower()

    m = _CANON_RE_LAYER_BRACKET.match(n)
    if m:
        li = int(m.group(1))
        field = str(m.group(2) or '').strip().lower()
        if field in ('enabled', 'opacity', 'blend_mode', 'order'):
            return ParsedAddress(scope='layer_field', key=field, layer_index=li, address=f'layers[{li}].{field}', was_alias=False)
        return None

    if n.startswith('layers[') and ']._op_overrides.' in n:
        try:
            left, key = n.split(']._op_overrides.', 1)
            li = int(left.split('[', 1)[1])
            if key in ('gain', 'gamma', 'posterize_levels'):
                return ParsedAddress(scope='operator_param', key=key, layer_index=li, address=f'layers[{li}]._op_overrides.{key}', was_alias=False)
        except Exception:
            return None
        return None

    if n.startswith('project.postfx.'):
        tail = n.split('project.postfx.', 1)[-1].strip()
        if tail in ('trail_amount', 'bleed_amount', 'bleed_radius'):
            return ParsedAddress(scope='project_postfx', key=tail, layer_index=None, address=f'project.postfx.{tail}', was_alias=False)
        return None

    if n in (
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
        if n.startswith('project.surface.mapping.'):
            key = n.split('project.surface.mapping.', 1)[-1]
        else:
            key = n.split('project.surface.', 1)[-1]
        return ParsedAddress(scope='project_layout', key=key, layer_index=None, address=n, was_alias=False)

    if n in (
        'project.spatial.enabled',
        'project.spatial.world_scale',
        'project.spatial.origin_x',
        'project.spatial.origin_y',
        'project.spatial.rotation_deg',
        'project.spatial.mirror_x',
        'project.spatial.mirror_y',
        'project.spatial.use_layout_coords',
    ):
        key = n.split('project.spatial.', 1)[-1]
        return ParsedAddress(scope='project_spatial', key=key, layer_index=None, address=n, was_alias=False)

    if n.startswith('project.variables.number.'):
        key = n.split('project.variables.number.', 1)[-1].strip()
        if key:
            return ParsedAddress(scope='project_variable', key=f'number.{key}', layer_index=None, address=f'project.variables.number.{key}', was_alias=False)
        return None

    if n.startswith('project.variables.toggle.'):
        key = n.split('project.variables.toggle.', 1)[-1].strip()
        if key:
            return ParsedAddress(scope='project_variable', key=f'toggle.{key}', layer_index=None, address=f'project.variables.toggle.{key}', was_alias=False)
        return None

    if n == 'project.ui.selected_layer':
        return ParsedAddress(scope='project_ui', key='selected_layer', layer_index=None, address='project.ui.selected_layer', was_alias=False)

    if n == 'project.ui.era_id':
        return ParsedAddress(scope='project_ui', key='era_id', layer_index=None, address='project.ui.era_id', was_alias=False)
    if n == 'project.ui.target_mask':
        return ParsedAddress(scope='project_ui', key='target_mask', layer_index=None, address='project.ui.target_mask', was_alias=False)

    if n == 'project.audio.routes':
        return ParsedAddress(scope='project_audio', key='routes', layer_index=None, address='project.audio.routes', was_alias=False)

    if n == 'project.audio.preset_name':
        return ParsedAddress(scope='project_audio', key='preset_name', layer_index=None, address='project.audio.preset_name', was_alias=False)

    if n.startswith('signals.'):
        key = raw[len('signals.'):].strip()
        if key:
            return ParsedAddress(scope='signal', key=key, layer_index=None, address=f'signals.{key}', was_alias=False)
        return None

    if n == 'systems.particles.total':
        return ParsedAddress(scope='system_state', key='particles.total', layer_index=None, address='systems.particles.total', was_alias=False)

    if n.startswith('systems.particles.'):
        tail = raw[len('systems.particles.'):].strip()
        parts = [p for p in tail.split('.') if p]
        if len(parts) == 2 and parts[1] in ('count', 'max_particles'):
            sys_name = parts[0].strip()
            if sys_name:
                return ParsedAddress(scope='system_state', key=f'particles.{sys_name}.{parts[1]}', layer_index=None, address=f'systems.particles.{sys_name}.{parts[1]}', was_alias=False)
        return None

    return None

def canonical_registry():
    return dict(CANONICAL_ADDRESS_REGISTRY)

def parse_bool(value) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return bool(float(value) != 0.0)
        except Exception:
            return None
    s = str(value).strip().lower()
    if s in {'1', '1.0', 'true', 'yes', 'on'}:
        return True
    if s in {'0', '0.0', 'false', 'no', 'off'}:
        return False
    return None

def clamp01(value) -> Optional[float]:
    try:
        v = float(value)
    except Exception:
        return None
    if v < 0.0:
        v = 0.0
    if v > 1.0:
        v = 1.0
    return v

def normalize_blend_mode(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().lower()
    if s == 'normal':
        s = 'over'
    return s if s in ALLOWED_BLEND_MODES else None
