from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from qt.qt_compat import QtWidgets


def _project_revision(app_core: Any) -> Any:
    for name in ("_project_revision", "project_revision", "revision"):
        value = getattr(app_core, name, None)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None
        if value is not None:
            return value
    return None


def _widget_label(widget: Any) -> str:
    for name in ("text", "title", "windowTitle", "placeholderText"):
        getter = getattr(widget, name, None)
        if callable(getter):
            try:
                value = getter()
            except Exception:
                value = None
            if value:
                return str(value)
    return ""


def _parent_chain(widget: Any) -> str:
    parts: List[str] = []
    current = widget
    guard = 0
    while current is not None and guard < 10:
        guard += 1
        try:
            cls = current.__class__.__name__
        except Exception:
            cls = type(current).__name__
        try:
            name = current.objectName() or ""
        except Exception:
            name = ""
        parts.append(f"{cls}('{name}')" if name else cls)
        try:
            current = current.parent()
        except Exception:
            break
    return " <- ".join(parts)


def _safe_button(widget: Any) -> tuple[bool, str]:
    text = (_widget_label(widget) or "").lower()
    name = (getattr(widget, 'objectName', lambda: '')() or '').lower()
    blocked = (
        'open', 'save', 'export', 'package', 'release', 'browse', 'choose', 'load',
        'delete', 'remove', 'clear', 'new project', 'quit', 'close', 'github', 'ota'
    )
    if any(token in text or token in name for token in blocked):
        return False, 'skipped:risky_button'
    return True, 'ok'


def run_ui_wiring_audit(owner: Any = None, app_core: Any = None) -> str:
    app = QtWidgets.QApplication.instance()
    if app is None:
        return "=== UI Wiring Audit ===\nERROR: QApplication not running"

    widgets = []
    for widget in list(QtWidgets.QApplication.allWidgets()):
        if owner is not None:
            try:
                if widget is not owner and not owner.isAncestorOf(widget):
                    continue
            except Exception:
                pass
        if not isinstance(widget, QtWidgets.QWidget):
            continue
        widgets.append(widget)

    lines: List[str] = ["=== UI Wiring Audit ==="]
    lines.append(f"widgets_scanned: {len(widgets)}")
    rev_before = _project_revision(app_core)

    summary: Dict[str, int] = {
        'buttons': 0, 'checks': 0, 'combos': 0, 'sliders': 0, 'tabs': 0,
        'triggered': 0, 'changed_revision': 0, 'errors': 0, 'skipped': 0,
    }
    details: List[Dict[str, Any]] = []

    def record(widget: Any, kind: str, action: str, outcome: str, changed: bool = False, error: Optional[str] = None):
        details.append({
            'kind': kind,
            'class': widget.__class__.__name__,
            'name': (widget.objectName() or ''),
            'label': _widget_label(widget),
            'action': action,
            'outcome': outcome,
            'changed_revision': changed,
            'error': error or '',
            'parents': _parent_chain(widget),
        })

    for widget in widgets:
        kind = None
        action = 'inspect'
        changed = False
        error = None
        outcome = 'ignored'
        rev0 = _project_revision(app_core)
        try:
            if isinstance(widget, QtWidgets.QPushButton) or isinstance(widget, QtWidgets.QToolButton):
                summary['buttons'] += 1
                kind = 'button'
                ok, note = _safe_button(widget)
                if not ok:
                    summary['skipped'] += 1
                    outcome = note
                else:
                    action = 'click'
                    widget.click()
                    QtWidgets.QApplication.processEvents()
                    outcome = 'clicked'
                    summary['triggered'] += 1
            elif isinstance(widget, QtWidgets.QCheckBox) or isinstance(widget, QtWidgets.QRadioButton):
                summary['checks'] += 1
                kind = 'check'
                action = 'toggle'
                state = bool(widget.isChecked())
                widget.setChecked(not state)
                QtWidgets.QApplication.processEvents()
                widget.setChecked(state)
                QtWidgets.QApplication.processEvents()
                outcome = 'toggled'
                summary['triggered'] += 1
            elif isinstance(widget, QtWidgets.QComboBox):
                summary['combos'] += 1
                kind = 'combo'
                count = int(widget.count())
                if count <= 1:
                    summary['skipped'] += 1
                    outcome = 'skipped:single_option'
                else:
                    action = 'change_index'
                    idx = int(widget.currentIndex())
                    alt = 0 if idx != 0 else 1
                    widget.setCurrentIndex(alt)
                    QtWidgets.QApplication.processEvents()
                    widget.setCurrentIndex(idx)
                    QtWidgets.QApplication.processEvents()
                    outcome = 'changed_index'
                    summary['triggered'] += 1
            elif isinstance(widget, QtWidgets.QSlider):
                summary['sliders'] += 1
                kind = 'slider'
                minimum = int(widget.minimum())
                maximum = int(widget.maximum())
                if minimum == maximum:
                    summary['skipped'] += 1
                    outcome = 'skipped:fixed_range'
                else:
                    action = 'set_value'
                    value = int(widget.value())
                    alt = minimum if value != minimum else maximum
                    widget.setValue(alt)
                    QtWidgets.QApplication.processEvents()
                    widget.setValue(value)
                    QtWidgets.QApplication.processEvents()
                    outcome = 'set_value'
                    summary['triggered'] += 1
            elif isinstance(widget, QtWidgets.QTabWidget):
                summary['tabs'] += 1
                kind = 'tabs'
                count = int(widget.count())
                if count <= 1:
                    summary['skipped'] += 1
                    outcome = 'skipped:single_tab'
                else:
                    action = 'switch_tab'
                    idx = int(widget.currentIndex())
                    alt = 0 if idx != 0 else 1
                    widget.setCurrentIndex(alt)
                    QtWidgets.QApplication.processEvents()
                    widget.setCurrentIndex(idx)
                    QtWidgets.QApplication.processEvents()
                    outcome = 'switched_tab'
                    summary['triggered'] += 1
        except Exception as exc:  # pragma: no cover - depends on live widgets
            summary['errors'] += 1
            error = f"{type(exc).__name__}: {exc}"
            outcome = 'error'

        rev1 = _project_revision(app_core)
        changed = rev0 is not None and rev1 is not None and rev1 != rev0
        if changed:
            summary['changed_revision'] += 1
        if kind is not None:
            record(widget, kind, action, outcome, changed=changed, error=error)

    lines.append(f"summary: {json.dumps(summary, sort_keys=True)}")
    if rev_before is not None:
        lines.append(f"project_revision_before: {rev_before}")
        lines.append(f"project_revision_after: {_project_revision(app_core)}")
    lines.append("")
    for row in details[:120]:
        bits = [f"{row['kind']}: {row['class']}"]
        if row['name']:
            bits.append(f"name={row['name']}")
        if row['label']:
            bits.append(f"label={row['label']}")
        bits.append(f"action={row['action']}")
        bits.append(f"outcome={row['outcome']}")
        bits.append(f"changed_revision={row['changed_revision']}")
        if row['error']:
            bits.append(f"error={row['error']}")
        lines.append("- " + "; ".join(bits))
    if len(details) > 120:
        lines.append(f"... truncated {len(details) - 120} additional control rows")
    return "\n".join(lines)
