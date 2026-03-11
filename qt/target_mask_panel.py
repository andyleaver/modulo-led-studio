try:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore
except ImportError:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore

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

class TargetMaskPanel(QtWidgets.QGroupBox):
    """Compact target mask selector extracted from qt_app.py.

    Delegates behavior to controller hooks:
      - _on_target_mask_changed
      - _clear_pixel_selection
    """

    def __init__(self, controller=None):
        super().__init__("Target Mask")
        self.controller = controller

        tlay = QtWidgets.QVBoxLayout(self)
        tlay.setContentsMargins(8, 8, 8, 8)
        tlay.setSpacing(6)

        top_row = QtWidgets.QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        top_row.addWidget(QtWidgets.QLabel("Mask:"), 0)
        self.target_mask_combo = QtWidgets.QComboBox()
        self.target_mask_combo.setToolTip("Optional global mask filter for preview. Uses project.ui.target_mask")
        top_row.addWidget(self.target_mask_combo, 1)

        self.btn_clear_sel = QtWidgets.QPushButton("Clear selection")
        self.btn_clear_sel.setToolTip("Clear current pixel selection")
        top_row.addWidget(self.btn_clear_sel, 0)

        tlay.addLayout(top_row)

        # Small hint row (kept subtle)
        hint = QtWidgets.QLabel("Applies as a global preview filter (does not modify layers).")
        hint.setWordWrap(True)
        try:
            hint.setStyleSheet("color: #888; font-size: 11px;")
        except Exception as e:
            _diag_exc(e, "qt/target_mask_panel.py")
        tlay.addWidget(hint)

        if controller is not None:
            try:
                self.target_mask_combo.installEventFilter(controller)
            except Exception as e:
                _diag_exc(e, "qt/target_mask_panel.py")
            if hasattr(controller, "_on_target_mask_changed"):
                try:
                    self.target_mask_combo.currentIndexChanged.connect(controller._on_target_mask_changed)
                except Exception as e:
                    _diag_exc(e, "qt/target_mask_panel.py")
            if hasattr(controller, "_clear_pixel_selection"):
                try:
                    self.btn_clear_sel.clicked.connect(controller._clear_pixel_selection)
                except Exception as e:
                    _diag_exc(e, "qt/target_mask_panel.py")

    def set_items(self, items, current_key=None):
        """Populate combo items: list of (label, key)"""
        self.target_mask_combo.blockSignals(True)
        self.target_mask_combo.clear()
        for label, key in items:
            self.target_mask_combo.addItem(label, key)
        # set current if provided
        if current_key is not None:
            for i in range(self.target_mask_combo.count()):
                if self.target_mask_combo.itemData(i) == current_key:
                    self.target_mask_combo.setCurrentIndex(i)
                    break
        self.target_mask_combo.blockSignals(False)

    def current_key(self):
        return self.target_mask_combo.currentData()
