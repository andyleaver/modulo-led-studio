from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


def _install_qt_stub(monkeypatch):
    qt_compat = types.ModuleType('qt.qt_compat')

    class _Signal:
        def connect(self, _fn):
            return None

    class _DummyWidget:
        def __init__(self, *_args, **_kwargs):
            return None
        def setMinimumHeight(self, _value):
            return None
        def setSizePolicy(self, *_args, **_kwargs):
            return None
        def update(self):
            return None

    class _DummyApp:
        @staticmethod
        def instance():
            return None

    class _Policy:
        Expanding = 1
        Fixed = 2

    class _DummyQObject: pass
    qt_compat.QtCore = types.SimpleNamespace(QObject=_DummyQObject)
    qt_compat.QtGui = types.SimpleNamespace()
    qt_compat.QtWidgets = types.SimpleNamespace(
        QApplication=_DummyApp,
        QSizePolicy=types.SimpleNamespace(Policy=_Policy),
        QWidget=_DummyWidget,
        QVBoxLayout=_DummyWidget,
        QHBoxLayout=_DummyWidget,
        QLabel=_DummyWidget,
        QComboBox=_DummyWidget,
        QGroupBox=_DummyWidget,
        QPushButton=_DummyWidget,
        QSpinBox=_DummyWidget,
        QCheckBox=_DummyWidget,
        QPlainTextEdit=_DummyWidget,
    )
    monkeypatch.setitem(sys.modules, 'qt.qt_compat', qt_compat)
    return qt_compat


def test_layout_panel_helpers_use_common_module() -> None:
    for rel in ['qt/layout_panel.py', 'qt/layout_panel_ui.py', 'qt/layout_panel_modes.py', 'qt/layout_panel_surface.py']:
        text = Path(rel).read_text(encoding='utf-8')
        assert 'qt.layout_panel_common' in text, rel
        assert 'from qt.layout_panel import' not in text, rel


def test_layout_panel_modules_import_without_circular_dependency(monkeypatch):
    _install_qt_stub(monkeypatch)
    for name in [
        'qt.layout_panel_common',
        'qt.wiretap',
        'qt.layout_panel_ui',
        'qt.layout_panel_modes',
        'qt.layout_panel_surface',
        'qt.layout_panel',
    ]:
        sys.modules.pop(name, None)
    wiretap_stub = types.ModuleType('qt.wiretap')
    class _WiretapLogPanel:
        def __init__(self, *_args, **_kwargs):
            return None
        def setMinimumHeight(self, _value):
            return None
    wiretap_stub.WiretapLogPanel = _WiretapLogPanel
    wiretap_stub.set_log_panel = lambda *_args, **_kwargs: None
    monkeypatch.setitem(sys.modules, 'qt.wiretap', wiretap_stub)
    common = importlib.import_module('qt.layout_panel_common')
    panel = importlib.import_module('qt.layout_panel')
    assert hasattr(common, 'diag_exc')
    assert hasattr(panel, 'LayoutPanel')
