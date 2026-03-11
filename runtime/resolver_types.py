from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from core.surface_compat import canonicalize_surface_geometry


@dataclass(frozen=True)
class Resolved:
    value: Any
    source: str


def _layer_dict(project: Any, i: int) -> Dict[str, Any]:
    try:
        layers = getattr(project, "layers", None)
        if isinstance(layers, list) and 0 <= i < len(layers):
            layer = layers[i]
            if isinstance(layer, dict):
                return layer
            try:
                data = vars(layer)
                if isinstance(data, dict):
                    return dict(data)
            except Exception:
                pass
    except Exception:
        pass
    try:
        layers = (project or {}).get("layers") if isinstance(project, dict) else None
        if isinstance(layers, list) and 0 <= i < len(layers):
            layer = layers[i]
            if isinstance(layer, dict):
                return layer
            try:
                data = vars(layer)
                if isinstance(data, dict):
                    return dict(data)
            except Exception:
                pass
    except Exception:
        pass
    return {}


def _layout_dict(project: Any) -> Dict[str, Any]:
    """Return the canonical surface dict for resolver reads.

    Canonical resolver addresses are project.surface.*.
    Runtime truth must come from project.surface, not from a root layout mirror.
    Any remaining root-level layout payload is migration/evidence territory only
    and must not participate in live resolver reads.
    """
    surf = None
    try:
        surf = getattr(project, "surface", None)
    except Exception:
        surf = None
    if not isinstance(surf, dict):
        try:
            if isinstance(project, dict):
                surf = project.get("surface")
        except Exception:
            surf = None
    if not isinstance(surf, dict):
        try:
            data = vars(surf)
            if isinstance(data, dict):
                surf = dict(data)
        except Exception:
            surf = None
    if not isinstance(surf, dict):
        return {}

    mapping = surf.get("mapping")
    if mapping is not None and not isinstance(mapping, dict):
        try:
            mdata = vars(mapping)
            if isinstance(mdata, dict):
                surf["mapping"] = dict(mdata)
        except Exception:
            pass

    layout = canonicalize_surface_geometry(surface=surf)
    layout.pop('type', None)
    return layout


def _spatial_dict(project: Any) -> Dict[str, Any]:
    try:
        sp = getattr(project, "spatial", None)
        if isinstance(sp, dict):
            return sp
    except Exception:
        pass
    try:
        if isinstance(project, dict):
            sp = project.get("spatial")
            if isinstance(sp, dict):
                return sp
    except Exception:
        pass
    return {}


def _ui_dict(project: Any) -> Dict[str, Any]:
    try:
        ui = getattr(project, "ui", None)
        if isinstance(ui, dict):
            return ui
    except Exception:
        pass
    try:
        if isinstance(project, dict):
            ui = project.get("ui")
            if isinstance(ui, dict):
                return ui
    except Exception:
        pass
    return {}


def _audio_dict(project: Any) -> Dict[str, Any]:
    try:
        if isinstance(project, dict):
            audio = project.get('audio')
            if isinstance(audio, dict):
                return dict(audio)
    except Exception:
        pass
    return {}
