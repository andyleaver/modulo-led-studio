from __future__ import annotations



# --- diagnostics helper (no silent failure) ---
try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None

def _diag_exc(e: Exception, where: str):
    try:
        if _DIAGS is not None:
            _DIAGS.exception(e, domain="UI", code="QT_UI_EXCEPTION", summary=where)
    except Exception:
        pass
try:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore
except Exception:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore

from qt.surface_preview_widget import SurfacePreviewWidget
from qt.tab_registry import build_tabs
from qt.splitters import restore_splitter


def build_header(owner, app_core):
    """Top strip line (Strip mode only).

    This must be *just* the coloured pixels with no extra bar/background.
    We show/hide it from QtMainWindow when layout switches between Strip/Cells.
    """
    owner.strip_header = QtWidgets.QWidget()
    lay = QtWidgets.QHBoxLayout(owner.strip_header)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)

    # Dedicated strip renderer: same codepath as matrix (SurfacePreviewWidget),
    # forced into 'strip' mode.
    owner.strip_mini = SurfacePreviewWidget(app_core, min_height=48, force_kind='strip')
    owner.strip_preview_widget = owner.strip_mini
    owner.strip_mini.setFixedHeight(48)
    lay.addWidget(owner.strip_mini)

    owner.strip_header.setFixedHeight(48)
    owner.strip_header.setVisible(False)
    return owner.strip_header


def build_controls_container(owner, app_core):
    """Main controls area (tabs) shown next to the cells preview."""
    w = QtWidgets.QWidget()
    v = QtWidgets.QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(6)

    # build_tabs() will create owner.tabs and add all panels.
    build_tabs(owner, v, app_core)

    return w


def build_matrix_preview(owner, app_core):
    """Build the body preview area around the shared surface preview widget."""

    owner.surface_preview = SurfacePreviewWidget(app_core)
    owner.surface_preview_widget = owner.surface_preview
    owner.preview_widget = owner.surface_preview
    owner.matrix_preview_widget = owner.surface_preview  # Alias for callers that still look up the preview by its older attribute name.

    # Right pane is cells-only. In Strip mode we show a "No preview" placeholder.
    owner.no_preview = QtWidgets.QLabel("No preview")
    # PySide6 moved alignment enums under Qt.AlignmentFlag in some versions.
    align_center = getattr(QtCore.Qt, 'AlignCenter', None)
    if align_center is None:
        align_center = QtCore.Qt.AlignmentFlag.AlignCenter
    owner.no_preview.setAlignment(align_center)
    owner.no_preview.setStyleSheet("color: #888; padding: 12px;")

    owner.preview_stack = QtWidgets.QStackedWidget()
    owner.preview_stack.addWidget(owner.surface_preview)  # index 0
    owner.preview_stack.addWidget(owner.no_preview)       # index 1

    try:
        owner.surface_preview.setMinimumWidth(420)
    except Exception as e:
        _diag_exc(e, "qt/layout_sections.py")

    return owner.preview_stack


def build_body_split(owner, controls_widget, matrix_preview):
    """Horizontal splitter: controls | cells preview."""
    try:
        ori = QtCore.Qt.Orientation.Horizontal
    except Exception:
        ori = QtCore.Qt.Horizontal

    owner.body_split = QtWidgets.QSplitter(ori)
    try:
        owner.body_split.setChildrenCollapsible(False)
    except Exception as e:
        _diag_exc(e, "qt/layout_sections.py")

    owner.body_split.addWidget(controls_widget)
    owner.body_split.addWidget(matrix_preview)

    # Defaults: prioritize *seeing all tabs* on first launch.
    # If the controls side is too narrow, Qt collapses the tab row into
    # scroll-buttons immediately, which feels broken.
    owner.body_split.setStretchFactor(0, 0)
    owner.body_split.setStretchFactor(1, 1)
    try:
        controls_widget.setMinimumWidth(860)
        owner.body_split.setSizes([920, 640])
    except Exception as e:
        _diag_exc(e, "qt/layout_sections.py")

    # Restore persisted splitter state (if any)
    restore_splitter(owner.body_split, "split/body_split")

    # Clamp after restore (and after the first layout pass) so the preview
    # cannot end up effectively invisible due to stale splitter settings.
    def _clamp():
        try:
            sizes = list(owner.body_split.sizes())
            if len(sizes) != 2:
                return
            controls_w, preview_w = sizes
            # If either side is effectively collapsed, reset to sane defaults.
            if preview_w < 360 or controls_w < 520:
                owner.body_split.setSizes([920, 640])
        except Exception:
            return

    try:
        QtCore.QTimer.singleShot(0, _clamp)
    except Exception:
        _clamp()


    return owner.body_split


def finalize_root(owner):
    """Attach main body to central widget."""
    root = QtWidgets.QWidget()
    root_lay = QtWidgets.QVBoxLayout(root)
    # Keep chrome tight so tabs are visible on first launch.
    root_lay.setContentsMargins(0, 0, 0, 0)
    root_lay.setSpacing(0)

    if getattr(owner, "strip_header", None) is not None:
        root_lay.addWidget(owner.strip_header, 0)
    root_lay.addWidget(owner.body_split, 1)

    owner.setCentralWidget(root)
    return root
