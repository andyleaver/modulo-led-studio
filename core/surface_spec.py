"""Canonical SurfaceSpec

Goal: one authoritative surface/mapping model consumed by BOTH preview and export.

This file intentionally avoids Qt and exporter-specific code.
"""

from __future__ import annotations

from core.surface_compat import canonical_surface_config, canonicalize_surface_geometry, get_surface_geometry_values, get_surface_kind_value, get_surface_mapping_values

# Optional diagnostics hook (core avoids hard dependency on runtime)
def _try_diag_exception(e: BaseException, code: str, summary: str = '', details: dict | None = None) -> None:
    try:
        from runtime.diagnostics import GLOBAL_DIAGS
        GLOBAL_DIAGS.exception(e, domain='MAPPING', code=code, summary=summary or code, details=details or {})
    except Exception:
        # diagnostics must never break core
        return

def _normalize_layout_for_surface_spec(layout: dict) -> dict:
    """Canonicalize a surface/layout dict for SurfaceSpec consumption.

    Runtime truth is canonical ``kind`` + nested ``mapping``. ``shape`` and flat
    mapping keys are migration-only evidence and are stripped from the returned
    live surface payload.
    """
    if layout is None:
        return {}
    try:
        raw = dict(layout)
    except Exception:
        return {}

    cfg = canonical_surface_config(raw)
    kind, count, w, h = get_surface_geometry_values(cfg, default_kind="strip", default_count=60)
    kind = str(kind or "strip").strip().lower()

    if kind == "cells":
        try:
            w = int(w or 0)
            h = int(h or 0)
        except Exception as e:
            _try_diag_exception(
                e,
                code="SURFACE_SPEC_NORMALIZE_DIMS_FAIL",
                summary="Failed to read canonical surface dims",
                details={"width": cfg.get("width"), "height": cfg.get("height")},
            )
            w = int(cfg.get("width") or 0)
            h = int(cfg.get("height") or 0)

        mapping = get_surface_mapping_values(cfg)
        out = canonicalize_surface_geometry({
            "kind": "cells",
            "width": int(w),
            "height": int(h),
            "count": int(count),
            "mapping": dict(mapping),
        })
        if "coords" in cfg:
            out["coords"] = cfg.get("coords")
        if "exists_mask" in cfg:
            out["exists_mask"] = cfg.get("exists_mask")
        return out

    try:
        c = int(count or 0)
    except Exception:
        c = 0
    mapping = get_surface_mapping_values(cfg)
    return canonicalize_surface_geometry({
        "kind": "strip",
        "count": int(max(0, c)),
        "width": int(max(0, c)),
        "height": 1,
        "mapping": dict(mapping),
    })

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

def _norm_str(x: Any, default: str = "") -> str:
    try:
        return str(x or default).strip()
    except Exception:
        return default

def _norm_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        try:
            return int(float(x))
        except Exception:
            return int(default)

def _norm_bool(x: Any, default: bool = False) -> bool:
    if isinstance(x, bool):
        return x
    if x is None:
        return default
    s = _norm_str(x).lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return default

@dataclass
class SurfaceSpec:
    """Authoritative description of the LED surface and its linearization."""

    kind: str = "strip"  # 'strip' or 'cells'
    width: int = 60
    height: int = 1
    count: int = 60

    # matrix mapping semantics
    serpentine: bool = False
    flip_x: bool = False
    flip_y: bool = False
    rotate: int = 0  # degrees: 0,90,180,270
    origin: str = "top_left"

    # Optional explicit coords list for cells surfaces.
    # coords[i] = (x,y) for logical index i.
    coords: Optional[List[Tuple[int, int]]] = None

    # Optional mask of existing pixels (e.g. non-rectangular topology)
    exists_mask: Optional[List[bool]] = None

    # Free-form extras (target/hardware hints)
    meta: Dict[str, Any] = field(default_factory=dict)

    # ---- Compatibility properties ------------------------------------------------
    # NOTE: Internally Modulo uses canonical names. Keep helper properties only
    # where they do not introduce legacy aliases back into live runtime meaning.
    @property
    def shape(self) -> str:
        """Canonical human-facing shape label."""
        k = (self.kind or "strip").lower()
        return "cells" if k == "cells" else "strip"

    @property
    def num_leds(self) -> int:
        return int(self.count)

    @property
    def mapping(self) -> Dict[str, Any]:
        """Canonical mapping flags (used by inspector/parity probes)."""
        return {
            "serpentine": bool(self.serpentine),
            "flip_x": bool(self.flip_x),
            "flip_y": bool(self.flip_y),
            "rotate": int(self.rotate),
            "origin": _norm_str(self.origin, "top_left"),
        }

    def summary(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "width": int(self.width),
            "height": int(self.height),
                        "serpentine": bool(self.serpentine),
            "flip_x": bool(self.flip_x),
            "flip_y": bool(self.flip_y),
            "rotate": int(self.rotate),
            "origin": _norm_str(self.origin, "top_left"),
            "coords": f"list[{len(self.coords)}]" if isinstance(self.coords, list) else None,
            "exists_mask": f"list[{len(self.exists_mask)}]" if isinstance(self.exists_mask, list) else None,
        }

    def to_layout_dict(self) -> Dict[str, Any]:
        """Layout dict for downstream components.

        Canonical dims keys are width/height.
        Legacy mw/mh/matrix_w/matrix_h are treated as import-only and must not
        be re-emitted.
        """
        if self.kind == "cells":
            mapping = get_surface_mapping_values(self)
            out = canonicalize_surface_geometry({
                "kind": "cells",
                "width": int(self.width),
                "height": int(self.height),
                "count": int(self.count),
                "mapping": dict(mapping),
            })
            out["coords"] = list(self.coords) if isinstance(self.coords, list) else None
            return out
        mapping = get_surface_mapping_values(self)
        return canonicalize_surface_geometry({
            "kind": "strip",
            "count": int(self.count),
            "width": int(self.count),
            "height": 1,
            "mapping": dict(mapping),
        })

def _generate_rect_coords(w: int, h: int) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    for y in range(int(h)):
        for x in range(int(w)):
            out.append((int(x), int(y)))
    return out

def surface_spec_from_layout(layout: Any) -> SurfaceSpec:
    """Normalize any of:

    - dict layout
    - object with layout fields

    into a canonical SurfaceSpec.
    """

    # read layout as dict-ish
    if isinstance(layout, dict):
        lay = layout
    else:
        # Object-backed callers should feed canonical surface fields only.
        # Deliberately do not revive legacy object mirrors such as ``shape`` or
        # root flat mapping flags here; live runtime callers should pass
        # ``kind`` + nested ``mapping`` instead.
        lay = {
            "kind": getattr(layout, "kind", None),
            "count": getattr(layout, "count", None),
            "width": getattr(layout, "width", None),
            "height": getattr(layout, "height", None),
            "coords": getattr(layout, "coords", None),
            "exists_mask": getattr(layout, "exists_mask", None),
            "mapping": getattr(layout, "mapping", None),
            "cell_size": getattr(layout, "cell_size", None),
            "cell": getattr(layout, "cell", None),
        }

    lay = _normalize_layout_for_surface_spec(lay)
    kind = get_surface_kind_value(lay, default="strip")

    if kind == "cells":
        mapping = get_surface_mapping_values(lay)
        _kind, _count, w, h = get_surface_geometry_values(lay, default_kind="cells", default_count=16 * 16)
        w = _norm_int(w or 16, 16)
        h = _norm_int(h or 16, 16)
        serp = _norm_bool(mapping.get("serpentine"), False)
        fx = _norm_bool(mapping.get("flip_x"), False)
        fy = _norm_bool(mapping.get("flip_y"), False)
        rot = _norm_int(mapping.get("rotate"), 0) % 360
        if rot not in (0, 90, 180, 270):
            rot = 0
        origin = _norm_str(mapping.get("origin"), "top_left") or "top_left"

        coords = lay.get("coords")
        if not (isinstance(coords, list) and coords and isinstance(coords[0], (list, tuple))):
            coords = _generate_rect_coords(w, h)
        else:
            # sanitize coords
            _c2: List[Tuple[int, int]] = []
            bad_pts = 0
            for pt in coords:
                try:
                    _c2.append((int(pt[0]), int(pt[1])))
                except Exception as e:
                    bad_pts += 1
            if bad_pts:
                _try_diag_exception(Exception('bad coord points'), code='SURFACE_SPEC_COORDS_SANITIZE', summary='Some coords entries were invalid and were dropped', details={'bad_pts': bad_pts, 'coords_len': len(coords) if isinstance(coords, list) else None, 'w': w, 'h': h})

            if len(_c2) != w * h:
                # fallback to rect to maintain determinism
                _c2 = _generate_rect_coords(w, h)
            coords = _c2

        return SurfaceSpec(
            kind="cells",
            width=int(w),
            height=int(h),
            count=int(w) * int(h),
            serpentine=bool(serp),
            flip_x=bool(fx),
            flip_y=bool(fy),
            rotate=int(rot),
            origin=origin,
            coords=list(coords),
        )

    # strip
    _kind, n, _w, _h = get_surface_geometry_values(lay, default_kind="strip", default_count=60)
    n = _norm_int(n or 60, 60)
    if n <= 0:
        n = 60

    # Minimal strip mapping flags. Treat strip as a 1-row surface.
    mapping = get_surface_mapping_values(lay)
    fx = _norm_bool(mapping.get("flip_x"), False)
    rot = _norm_int(mapping.get("rotate"), 0) % 360
    if rot not in (0, 180):
        # 90/270 don't have a meaningful 1D interpretation (keep deterministic).
        rot = 0
    origin = _norm_str(mapping.get("origin"), "top_left") or "top_left"

    return SurfaceSpec(
        kind="strip",
        width=int(n),
        height=1,
        count=int(n),
        serpentine=False,
        flip_x=bool(fx),
        flip_y=False,
        rotate=int(rot),
        origin=origin,
    )

    def _positive_int(self, v, default=0):
        try:
            iv = int(v)
            return iv if iv > 0 else default
        except Exception:
            return default

    def is_valid(self) -> bool:
        """Conservative validity check to prevent blank previews if layout keys are missing."""
        if getattr(self, "kind", None) == "strip":
            return self._positive_int(getattr(self, "count", 0)) > 0
        if getattr(self, "kind", None) == "cells":
            w = self._positive_int(getattr(self, "width", 0))
            h = self._positive_int(getattr(self, "height", 0))
            return w > 0 and h > 0
        return False
