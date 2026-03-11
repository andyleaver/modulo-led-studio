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

    class _DummyTimer:
        def __init__(self, *_args, **_kwargs):
            self.timeout = _Signal()
        def setInterval(self, _value):
            return None
        def start(self):
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
        def processEvents():
            return None

    class _DummyPainter:
        class RenderHint:
            Antialiasing = 1
        def __init__(self, *_args, **_kwargs):
            return None
        def setRenderHint(self, *_args, **_kwargs):
            return None
        def fillRect(self, *_args, **_kwargs):
            return None
        def setPen(self, *_args, **_kwargs):
            return None
        def setBrush(self, *_args, **_kwargs):
            return None
        def drawRoundedRect(self, *_args, **_kwargs):
            return None
        def drawEllipse(self, *_args, **_kwargs):
            return None

    class _DummyColor:
        def __init__(self, *_args, **_kwargs):
            return None

    class _DummyPen:
        def __init__(self, *_args, **_kwargs):
            return None

    class _Policy:
        Expanding = 1
        Fixed = 2

    qt_compat.QtCore = types.SimpleNamespace(QTimer=_DummyTimer)
    qt_compat.QtGui = types.SimpleNamespace(QColor=_DummyColor, QPainter=_DummyPainter, QPen=_DummyPen)
    qt_compat.QtWidgets = types.SimpleNamespace(QApplication=_DummyApp, QSizePolicy=types.SimpleNamespace(Policy=_Policy), QWidget=_DummyWidget)
    monkeypatch.setitem(sys.modules, 'qt.qt_compat', qt_compat)
    return qt_compat


def test_preview_engine_imports_math_and_geometry_alias():
    mod = importlib.import_module('preview.engine')
    assert hasattr(mod, 'math')
    assert mod.Geometry is mod.GridGeom


def test_full_audit_probes_has_live_path_import():
    mod = importlib.import_module('qt.diagnostics_console_full_audit_probes')
    assert 'Path' in mod._artifact_run_dir.__globals__
    run_dir = mod._artifact_run_dir('PASS15_TEST')
    assert run_dir.name == 'PASS15_TEST'


def test_diagnostics_console_modules_have_live_support_imports(monkeypatch):
    _install_qt_stub(monkeypatch)
    sys.modules.pop('qt.diagnostics_console_audit_state', None)
    sys.modules.pop('qt.diagnostics_console_doors_execution', None)
    audit_state = importlib.import_module('qt.diagnostics_console_audit_state')
    doors_exec = importlib.import_module('qt.diagnostics_console_doors_execution')
    assert hasattr(audit_state, 'time')
    assert hasattr(doors_exec, 'time')
    assert hasattr(doors_exec, 'json')
    assert hasattr(doors_exec, 'QtWidgets')


def test_era_panel_preview_uses_qt_compat_and_imports_cleanly(monkeypatch):
    _install_qt_stub(monkeypatch)
    sys.modules.pop('qt.era_panel_preview', None)
    mod = importlib.import_module('qt.era_panel_preview')
    assert hasattr(mod, '_WorkbenchPreview')
    preview = mod._WorkbenchPreview()
    assert preview is not None


def test_help_text_references_artifacts_path():
    text = (Path('app') / 'help_texts.py').read_text(encoding='utf-8')
    assert '../artifacts/' in text
