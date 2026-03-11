from __future__ import annotations

"""Public canonical resolver facade.

This module is the stable import surface for preview, export, UI, diagnostics,
and rules. Canonical read truth lives in ``runtime.resolver_read`` and canonical
write truth lives in ``runtime.resolver_write``; this facade deliberately re-
exports those entry points so the rest of the codebase goes through one public
resolver door.
"""

from runtime.resolver_read import (
    resolve_address,
    resolve_layer_field,
    resolve_project_audio_field,
    resolve_project_layout_field,
    resolve_project_postfx,
    resolve_project_spatial_field,
    resolve_project_surface_field,
    resolve_project_ui_field,
    resolve_project_variable,
    resolve_signal_value,
    resolve_system_state,
    resolver_registry,
)
from runtime.resolver_write import set_address

__all__ = [
    'get_address',
    'resolve_address',
    'resolve_layer_field',
    'resolve_project_audio_field',
    'resolve_project_layout_field',
    'resolve_project_postfx',
    'resolve_project_spatial_field',
    'resolve_project_surface_field',
    'resolve_project_ui_field',
    'resolve_project_variable',
    'resolve_signal_value',
    'resolve_system_state',
    'resolver_registry',
    'set_address',
]


def get_address(project, address: str, runtime=None, default=None):
    """Compatibility read helper returning the resolved value only."""
    try:
        return resolve_address(project=project, address=address, runtime=runtime, default=default).value
    except Exception:
        return default
