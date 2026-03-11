"""Canonical preview/project bridge helpers for CoreBridge.

This module keeps all preview ingestion paths on one canonical route:
project dict -> sanitize -> canonical loader -> preview model/geometry.
"""

from __future__ import annotations

from preview.preview_project_bridge import prepare_preview_project as _canonical_prepare_preview_project
from core.surface_compat import get_surface_geometry_values, normalize_surface_mapping

def prepare_preview_project(project_dict: dict, *, root_dir: str | None = None) -> tuple[object, list, dict]:
    return _canonical_prepare_preview_project(project_dict, root_dir=root_dir)

def build_preview_geometry_from_snapshot(snapshot: dict):
    """Build preview geometry from canonical surface snapshot."""
    from preview.engine import build_strip_geom, build_cells_geom

    snap = snapshot if isinstance(snapshot, dict) else {}
    kind, count, width, height = get_surface_geometry_values(snap, default_kind="strip", default_count=1)
    mapping = normalize_surface_mapping(snap.get("mapping"), fallback=snap)

    if kind == "cells":
        try:
            cell = float(snap.get("cell") or snap.get("cell_size") or 20)
        except Exception:
            cell = 20.0
        if cell <= 0:
            cell = 20.0
        return build_cells_geom(
            int(width),
            int(height),
            float(cell),
            serpentine=mapping['serpentine'],
            flip_x=mapping['flip_x'],
            flip_y=mapping['flip_y'],
            rotate=mapping['rotate'],
            origin=mapping['origin'],
        )

    return build_strip_geom(int(count))

def reapply_runtime_only_preview_state(src_proj: dict, proj_obj: object) -> None:
    """Restore in-memory runtime-only preview fields stripped by canonical loader."""
    try:
        src_proj = src_proj if isinstance(src_proj, dict) else {}
        src_pfx = src_proj.get("postfx") if isinstance(src_proj, dict) else None
        rt_key = src_pfx.get("_rt_cache_key") if isinstance(src_pfx, dict) else None
        if rt_key:
            dst_pfx = getattr(proj_obj, "postfx", None)
            if not isinstance(dst_pfx, dict):
                dst_pfx = {}
            else:
                dst_pfx = dict(dst_pfx)
            dst_pfx["_rt_cache_key"] = rt_key
            setattr(proj_obj, "postfx", dst_pfx)

        src_layers = src_proj.get("layers") if isinstance(src_proj, dict) else None
        dst_layers = getattr(proj_obj, "layers", None)
        if isinstance(src_layers, list) and isinstance(dst_layers, list):
            for i, src_layer in enumerate(src_layers):
                if i >= len(dst_layers) or not isinstance(src_layer, dict):
                    continue
                ov = src_layer.get("_op_overrides")
                if not isinstance(ov, dict) or not ov:
                    continue
                dst_layer = dst_layers[i]
                try:
                    setattr(dst_layer, "_op_overrides", dict(ov))
                except Exception:
                    try:
                        if isinstance(dst_layer, dict):
                            dst_layer["_op_overrides"] = dict(ov)
                    except Exception:
                        pass
    except Exception:
        pass
