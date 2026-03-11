from __future__ import annotations

import time

try:
    from qt.qt_compat import QtCore, QtGui, QtWidgets  # type: ignore
except Exception:  # pragma: no cover
    from qt.qt_compat import QtCore, QtGui, QtWidgets  # type: ignore

try:
    from app.project_model import get_surface_spec, get_surface_snapshot, get_surface_kind, get_surface_mapping, get_surface_geometry_values, get_surface_count
except Exception:
    get_surface_spec = None  # type: ignore
    get_surface_snapshot = None  # type: ignore
    get_surface_kind = None  # type: ignore
    get_surface_mapping = None  # type: ignore
    get_surface_geometry_values = None  # type: ignore
    get_surface_count = None  # type: ignore

from core.surface_compat import normalize_surface_mapping
from preview.viewport import Viewport
from preview.mapping import MatrixMapping, xy_index, logical_dims
from export.targets.registry import load_target
from export.gating import gate_project_for_target


def pick_debug_color(index: int) -> tuple[int, int, int]:
    palette = [
        (255, 99, 132),
        (54, 162, 235),
        (255, 206, 86),
        (75, 192, 192),
        (153, 102, 255),
        (255, 159, 64),
        (46, 204, 113),
        (241, 196, 15),
    ]
    return palette[int(index) % len(palette)]
