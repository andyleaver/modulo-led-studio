from __future__ import annotations

from qt.layout_panel_common import QtWidgets, diag_exc as _diag_exc

from qt.layout_panel_ui import LayoutPanelUiMixin
from qt.layout_panel_modes import LayoutPanelModesMixin
from qt.layout_panel_surface import LayoutPanelSurfaceMixin


class LayoutPanel(
    QtWidgets.QWidget,
    LayoutPanelUiMixin,
    LayoutPanelModesMixin,
    LayoutPanelSurfaceMixin,
):
    def __init__(self, app_core, controller=None, on_layout_changed_cb=None, parent=None):
        super().__init__(parent)
        self.app_core = app_core
        self.controller = controller
        self.on_layout_changed_cb = on_layout_changed_cb
        self._preview_widget = getattr(controller, 'surface_preview_widget', None) if controller is not None else None
        self._build_ui()
        self._wire_signals()
        self.sync_from_project()
        self._apply_surface_gate()
        self._apply_studio_mode_gate()
        self._refresh_visibility()
