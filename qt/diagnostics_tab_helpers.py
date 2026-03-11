from __future__ import annotations

import json

try:
    from qt.qt_compat import QtWidgets  # type: ignore
except Exception:
    from qt.qt_compat import QtWidgets  # type: ignore


def pretty_text(obj) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (list, dict)):
        try:
            return json.dumps(obj, indent=2, sort_keys=False)
        except Exception:
            return str(obj)
    return str(obj)


def parent_chain(widget) -> str:
    try:
        parts = []
        current = widget
        guard = 0
        while current is not None and guard < 40:
            guard += 1
            try:
                name = current.objectName() if hasattr(current, "objectName") else ""
            except Exception:
                name = ""
            try:
                cls = current.__class__.__name__
            except Exception:
                cls = str(type(current))
            parts.append(f"{cls}('{name}')" if name else cls)
            try:
                current = current.parent()
            except Exception:
                break
        return " <- ".join(parts)
    except Exception:
        return "(parent chain unavailable)"


def project_data(app_core, controller=None):
    pd = getattr(app_core, "project_data", None)
    if callable(pd):
        try:
            pd = pd()
        except Exception:
            pd = None
    if isinstance(pd, dict):
        return pd
    project = getattr(app_core, "project", None)
    if callable(project):
        try:
            project = project()
        except Exception:
            project = None
    if isinstance(project, dict):
        return project
    if controller is not None:
        bridge = getattr(controller, "bridge", None)
        if bridge is not None:
            project = getattr(bridge, "project", None)
            if callable(project):
                try:
                    project = project()
                except Exception:
                    project = None
            if isinstance(project, dict):
                return project
    return {}


def runtime_data(app_core, controller=None):
    runtime = {}
    try:
        getter = getattr(app_core, 'get_runtime_variables_state', None)
        values = getter() if callable(getter) else getter
        if isinstance(values, dict):
            runtime['variables'] = values
    except Exception:
        pass
    try:
        getter = getattr(app_core, 'get_signal_snapshot', None)
        values = getter() if callable(getter) else getter
        if isinstance(values, dict):
            runtime['signals'] = values
    except Exception:
        pass
    if controller is not None:
        try:
            bridge = getattr(controller, 'bridge', None)
            if bridge is not None:
                if 'variables' not in runtime:
                    getter = getattr(bridge, 'get_runtime_variables_state', None)
                    values = getter() if callable(getter) else getter
                    if isinstance(values, dict):
                        runtime['variables'] = values
                if 'signals' not in runtime:
                    getter = getattr(bridge, 'get_signal_snapshot', None)
                    values = getter() if callable(getter) else getter
                    if isinstance(values, dict):
                        runtime['signals'] = values
        except Exception:
            pass
    return runtime


def qapplication_instance():
    app = QtWidgets.QApplication.instance()
    return app


def all_widgets():
    return list(QtWidgets.QApplication.allWidgets())
