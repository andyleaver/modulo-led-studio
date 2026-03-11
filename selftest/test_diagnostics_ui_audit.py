from __future__ import annotations

import pytest

pytest.importorskip("qt.qt_compat")

from app.ui_wiring_audit import run_ui_wiring_audit
from qt.qt_compat import QtWidgets


class _Core:
    def __init__(self) -> None:
        self._project_revision = 0


def _app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_ui_wiring_audit_reports_safe_controls() -> None:
    _app()
    core = _Core()
    owner = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(owner)
    button = QtWidgets.QPushButton('Run Probe')
    button.setObjectName('run_probe')
    button.clicked.connect(lambda: setattr(core, '_project_revision', core._project_revision + 1))
    combo = QtWidgets.QComboBox()
    combo.addItems(['one', 'two'])
    combo.currentIndexChanged.connect(lambda _i: setattr(core, '_project_revision', core._project_revision + 1))
    check = QtWidgets.QCheckBox('Enabled')
    check.toggled.connect(lambda _v: setattr(core, '_project_revision', core._project_revision + 1))
    tabs = QtWidgets.QTabWidget()
    tabs.addTab(QtWidgets.QWidget(), 'A')
    tabs.addTab(QtWidgets.QWidget(), 'B')
    layout.addWidget(button)
    layout.addWidget(combo)
    layout.addWidget(check)
    layout.addWidget(tabs)
    owner.show()
    QtWidgets.QApplication.processEvents()

    report = run_ui_wiring_audit(owner=owner, app_core=core)

    assert '=== UI Wiring Audit ===' in report
    assert 'clicked' in report
    assert 'changed_index' in report
    assert 'toggled' in report
    assert 'switched_tab' in report
