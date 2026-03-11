"""Qt main window layout orchestration."""

from __future__ import annotations

try:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore
except Exception:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore

from qt.window_chrome import set_window_title
from qt.layout_helpers import _install_global_excepthook, _normalize_project
from qt.layout_sections import (
    build_header,
    build_controls_container,
    build_matrix_preview,
    build_body_split,
    finalize_root,
)

def build_main_layout(owner, app_core):
    """Build the QtMainWindow UI layout (splitters, central widgets, menus)."""
    # Title / fatal error dialog wiring
    set_window_title(owner, getattr(owner, "APP_ID", ""))
    _install_global_excepthook()

    # Keep project model stable early.
    try:
        _normalize_project(app_core.project)
    except Exception:
        pass

    # Sections
    build_header(owner, app_core)
    controls = build_controls_container(owner, app_core)
    matrix = build_matrix_preview(owner, app_core)
    build_body_split(owner, controls, matrix)
    finalize_root(owner)

    # Sync initial mode.
    try:
        owner._on_layout_changed()
    except Exception:
        pass

    # One-shot startup flag used during initial UI wiring
    owner._did_post_startup = False
