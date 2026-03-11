from __future__ import annotations
from qt.era_ui_gate import apply_ui_gates
"""Qt application."""

import sys
import time

from qt.main_window_support import (
    APP_ID,
    APP_TITLE,
    BETA_DETERMINISTIC_SIGNAL_SET,
    BETA_TARGET_CAPABILITIES,
    install_global_excepthook as _install_global_excepthook,
    make_hline as _hline,
    normalize_project_for_editor as _normalize_project,
)

# Signals inspector panel
try:
    from qt.signals_panel import SignalsPanel
except Exception:
    SignalsPanel = None  # type: ignore

# Phase 6.2: Variables panel
try:
    from qt.variables_panel import VariablesPanel
except Exception:
    VariablesPanel = None  # type: ignore

try:
    from qt.qt_compat import QtCore, QtGui, QtWidgets  # type: ignore
    from qt.diagnostics_console import DiagnosticsConsole
    _BINDING = "PySide6"
except Exception:  # pragma: no cover
    from qt.qt_compat import QtCore, QtGui, QtWidgets  # type: ignore
    from qt.diagnostics_console import DiagnosticsConsole
    _BINDING = "PyQt6"

# : Parameter Registry MVP (Qt auto-controls)
from params.registry import PARAMS
from params.ensure import ensure_params, defaults_for
from behaviors.registry import get_effect, load_capabilities_catalog

from preview.viewport import Viewport
from preview.mapping import MatrixMapping, xy_index, logical_dims
from export.targets.registry import load_target
from export.gating import gate_project_for_target
from qt.era_panel import EraPanel
from qt.era_onboarding import EraOnboardingWindow
from app.eras.era_runtime_bridge import install_era_runtime_bridge
import json


# Qt6 binding compatibility
try:
    _ORI_H = QtCore.Qt.Horizontal  # Qt5 style
except Exception:
    _ORI_H = QtCore.Qt.Orientation.Horizontal  # Qt6 style


from qt.tab_registry import build_tabs
from qt.main_layout import build_main_layout
from qt.wiretap import install_wiretap
from qt.main_window_logic import MainWindowLogicMixin

class QtMainWindow(MainWindowLogicMixin, QtWidgets.QMainWindow):
    def __init__(self, app_core):
            super().__init__()
            self.setWindowTitle(f"{APP_TITLE} — {APP_ID}")

            # Ensure the OS/window-manager treats this as a normal resizable main window
            # (some WMs disable maximize if the window type/hints look like a tool/dialog).
            try:
                flags = self.windowFlags()
                flags |= QtCore.Qt.WindowType.Window
                flags |= QtCore.Qt.WindowType.WindowMaximizeButtonHint
                flags |= QtCore.Qt.WindowType.WindowMinimizeButtonHint
                flags |= QtCore.Qt.WindowType.WindowCloseButtonHint
                self.setWindowFlags(flags)
            except Exception:
                pass

            self.app_core = app_core
            try:
                install_era_runtime_bridge(self.app_core)
            except Exception:
                pass

            # Diagnostics Console (dockable). Toggle with F12.
            try:
                self._diag_console = DiagnosticsConsole(app_core, parent=self)
                self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self._diag_console)
                self._diag_console.hide()
                act = QtGui.QAction(self)
                act.setShortcuts([QtGui.QKeySequence('F12'), QtGui.QKeySequence('Ctrl+Shift+D')])
                act.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
                act.triggered.connect(self._toggle_diagnostics_console)
                self.addAction(act)
                # Also add to View menu so users don't need shortcuts
                try:
                    mb = self.menuBar()
                    view_menu = None
                    for a in mb.actions():
                        if a.text().replace('&','').lower() == 'view':
                            view_menu = a.menu()
                            break
                    if view_menu is None:
                        view_menu = mb.addMenu('&View')
                    act.setText('Diagnostics Console')
                    view_menu.addAction(act)
                except Exception:
                    pass
            except Exception as e:
                import traceback as _tb
                try:
                    tb = _tb.format_exc()
                    print('[DiagnosticsConsole] INIT FAILED')
                    print(tb)
                    try:
                        import os as _os
                        run_root = getattr(self.core, 'run_root', None)
                        if run_root is None:
                            run_root = _os.getcwd()
                        p = _os.path.join(str(run_root), 'user_data', 'logs')
                        _os.makedirs(p, exist_ok=True)
                        fn = _os.path.join(p, 'diagnostics_console_init_fail.log')
                        with open(fn, 'w', encoding='utf-8') as f:
                            f.write(tb)
                    except Exception:
                        pass
                    self._diag_console_fail_banner('Diagnostics Console failed to initialize. See user_data/logs/diagnostics_console_init_fail.log')
                except Exception:
                    pass
                self._diag_console = None
            build_main_layout(self, app_core)
            try:
                self._maybe_launch_era_onboarding()
            except Exception:
                pass
            try:
                from qt.qt_compat import QtWidgets
                self._workflow_banner = QtWidgets.QLabel("Workflow: Surface → Layers → Behaviour → Inputs → Preview → Export")
                self._workflow_banner.setWordWrap(True)
                self.statusBar().addPermanentWidget(self._workflow_banner)

                self._workflow_step = QtWidgets.QLabel("Current Step: Surface")
                self.statusBar().addPermanentWidget(self._workflow_step)

                self._workflow_mode = QtWidgets.QLabel("Mode: Full Modulo")
                self.statusBar().addPermanentWidget(self._workflow_mode)
            except Exception:
                pass
            # Studio startup should land on the first real creation step: Surface / Hardware.
            # Era onboarding remains separate; once in studio, start on Surface unless a gated
            # preferred tab is explicitly returned by the existing studio preference logic.
            try:
                if hasattr(self, 'tabs'):
                    start_idx = 0
                    try:
                        gates = getattr(self.app_core, 'get_era_gates', lambda: {})() or {}
                        stop_here_ok = bool(gates.get('stop_here_ok', False))
                        era_complete = bool(getattr(self.app_core, 'is_era_complete', lambda: False)())
                        if era_complete or stop_here_ok:
                            preferred = self._preferred_studio_tab_index(
                                gates=gates,
                                focus_modulo=era_complete
                            )
                            # Keep Surface / Hardware as the baseline studio landing tab.
                            start_idx = int(preferred) if isinstance(preferred, int) and preferred >= 0 else 0
                        else:
                            start_idx = 0
                    except Exception:
                        start_idx = 0
                    self.tabs.setCurrentIndex(int(start_idx))
                    try:
                        saved_mode = self._load_studio_mode()
                        self._apply_studio_mode(saved_mode)
                    except Exception:
                        pass
                    try:
                        apply_ui_gates(self)
                    except Exception:
                        pass
            except Exception:
                pass

