"""Compatibility wrapper for preview widgets.

Canonical implementation is split across focused modules:
- qt.preview_strip_widgets
- qt.preview_matrix_widgets
"""
from __future__ import annotations

from qt.preview_strip_widgets import APP_TITLE, _install_global_excepthook, StripMiniPreview, StripPreviewBar
from qt.preview_matrix_widgets import PreviewWidget, MatrixPreviewWidget

__all__ = [
    "APP_TITLE",
    "_install_global_excepthook",
    "StripMiniPreview",
    "StripPreviewBar",
    "PreviewWidget",
    "MatrixPreviewWidget",
]
