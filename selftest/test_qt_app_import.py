from __future__ import annotations

import importlib
import sys
import types


def _install_qt_compat_stub() -> None:
    mod = types.ModuleType('qt.qt_compat')

    class _App:
        @staticmethod
        def instance():
            return None

    class _MessageBox:
        @staticmethod
        def critical(*args, **kwargs):
            return None

    mod.QtWidgets = types.SimpleNamespace(QApplication=_App, QMessageBox=_MessageBox)
    sys.modules['qt.qt_compat'] = mod


def test_qt_app_import_exposes_live_diag_helper():
    _install_qt_compat_stub()
    sys.modules.pop('qt.qt_app', None)
    mod = importlib.import_module('qt.qt_app')
    assert callable(mod._diag_exc)
    assert callable(mod._install_global_excepthook)
