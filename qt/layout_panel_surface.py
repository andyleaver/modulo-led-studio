from __future__ import annotations

from runtime.resolver import set_address
from app.project_model import get_surface_count, get_surface_dimensions, get_surface_kind, get_surface_mapping
from core.surface_compat import normalize_surface_mapping
from qt.layout_panel_common import QtWidgets, diag_exc as _diag_exc


def get_project(app_core) -> dict:
    project = getattr(app_core, 'project', None)
    return project if isinstance(project, dict) else {}


def notify_project_changed(app_core, diag_exc):
    for name in ('on_project_changed', 'mark_dirty', 'set_dirty', 'notify_project_changed'):
        fn = getattr(app_core, name, None)
        if callable(fn):
            try:
                fn()
                return
            except Exception as exc:
                diag_exc(exc, 'qt/layout_panel.py.notify_project_changed')


def apply_layout_to_project(panel, is_cells: bool, diag_exc):
    project = get_project(panel.app_core)
    changed = False
    if is_cells:
        writes = [
            ('project.surface.kind', 'cells'),
            ('project.surface.width', int(panel.w_spin.value())),
            ('project.surface.height', int(panel.h_spin.value())),
            ('project.surface.mapping.serpentine', bool(panel.cb_serp.isChecked())),
            ('project.surface.mapping.flip_x', bool(panel.cb_flipx.isChecked())),
            ('project.surface.mapping.flip_y', bool(panel.cb_flipy.isChecked())),
        ]
    else:
        writes = [
            ('project.surface.kind', 'strip'),
            ('project.surface.count', int(panel.strip_count.value())),
            ('project.surface.mapping.flip_x', bool(panel.strip_reverse.isChecked())),
        ]
    pm = getattr(panel.app_core, 'pm', None)
    if pm is not None and hasattr(pm, 'guarded_set_address'):
        try:
            for addr, value in writes:
                changed = bool(pm.guarded_set_address(addr, value)) or changed
            if hasattr(pm, 'get'):
                project = pm.get(); panel.app_core.project = project
        except Exception as exc:
            diag_exc(exc, 'qt/layout_panel.py.apply_layout_to_project')
    else:
        for addr, value in writes:
            project, did = set_address(project=project, address=addr, value=value)
            changed = changed or bool(did)
        try:
            panel.app_core.project = project
        except Exception as exc:
            diag_exc(exc, 'qt/layout_panel.py.apply_layout_to_project')
    if changed:
        notify_project_changed(panel.app_core, diag_exc)
    return project, changed


def sync_widgets_from_project(panel):
    project = get_project(panel.app_core)
    is_cells = (get_surface_kind(project) == 'cells')
    width, height = get_surface_dimensions(project)
    count = get_surface_count(project)
    mapping = normalize_surface_mapping(get_surface_mapping(project))
    panel.layout_combo.blockSignals(True); panel.layout_combo.setCurrentIndex(1 if is_cells else 0); panel.layout_combo.blockSignals(False)
    if is_cells:
        for widget in (panel.w_spin, panel.h_spin, panel.cb_serp, panel.cb_flipx, panel.cb_flipy):
            widget.blockSignals(True)
        panel.w_spin.setValue(int(width or 64))
        panel.h_spin.setValue(int(height or 32))
        panel.cb_serp.setChecked(bool(mapping.get('serpentine', False)))
        panel.cb_flipx.setChecked(bool(mapping.get('flip_x', False)))
        panel.cb_flipy.setChecked(bool(mapping.get('flip_y', False)))
        for widget in (panel.w_spin, panel.h_spin, panel.cb_serp, panel.cb_flipx, panel.cb_flipy):
            widget.blockSignals(False)
    panel.strip_count.blockSignals(True); panel.strip_reverse.blockSignals(True)
    panel.strip_count.setValue(int(count or 60))
    panel.strip_reverse.setChecked(bool(mapping.get('flip_x', False)))
    panel.strip_count.blockSignals(False); panel.strip_reverse.blockSignals(False)
    return project, is_cells


class LayoutPanelSurfaceMixin:
    def _wiretap_log(self, msg: str):
        try:
            wiretap = getattr(getattr(self, 'app_core', None), 'wiretap', None)
            if wiretap is not None and hasattr(wiretap, 'log'):
                wiretap.log(msg); return
        except Exception as exc:
            _diag_exc(exc, 'qt/layout_panel.py.wiretap_log')
        try:
            print(msg)
        except Exception:
            pass

    def _project(self) -> dict:
        return get_project(self.app_core)

    def sync_from_project(self):
        try:
            sync_widgets_from_project(self)
            self._refresh_visibility()
        except Exception as exc:
            _diag_exc(exc, 'qt/layout_panel.py.sync_from_project')

    def _notify_layout_changed(self):
        callback = getattr(self, 'on_layout_changed_cb', None)
        if callable(callback):
            try:
                callback(); return
            except Exception as exc:
                _diag_exc(exc, 'qt/layout_panel.py.notify_layout_changed')
        ctrl = getattr(self, 'controller', None)
        if ctrl is not None:
            for attr in ('_on_layout_changed', '_layout_changed', 'on_layout_changed'):
                fn = getattr(ctrl, attr, None)
                if callable(fn):
                    try:
                        fn()
                    except Exception as exc:
                        _diag_exc(exc, f'qt/layout_panel.py.{attr}')
                    break

    def _apply_surface_preset(self, *, kind: str, count: int | None = None, width: int | None = None, height: int | None = None):
        try:
            project = dict(self._project() or {})
            writes = [("project.surface.kind", "cells" if str(kind).lower() == "cells" else "strip")]
            if count is not None:
                writes.append(("project.surface.count", int(count)))
            if width is not None:
                writes.append(("project.surface.width", int(width)))
            if height is not None:
                writes.append(("project.surface.height", int(height)))
            for addr, value in writes:
                project, _did = set_address(project=project, address=addr, value=value)
            self.app_core.project = project
            notify_project_changed(self.app_core, _diag_exc)
            self.sync_from_project(); self._apply_surface_gate(); self._apply_studio_mode_gate(); self._refresh_visibility(); self._notify_layout_changed()
        except Exception as exc:
            _diag_exc(exc, 'qt/layout_panel.py.surface_preset')

    def _refresh_visibility(self):
        is_matrix = self.layout_combo.currentIndex() == 1
        self.matrix_box.setVisible(is_matrix)
        self.strip_box.setVisible(not is_matrix)

    def _on_layout_changed(self):
        self._refresh_visibility()
        apply_layout_to_project(self, self.layout_combo.currentIndex() == 1, _diag_exc)
        self._notify_layout_changed()

    def _on_matrix_changed(self):
        try:
            if self.controller is not None:
                for attr in ('_matrix_dims_changed', '_matrix_mapping_changed'):
                    fn = getattr(self.controller, attr, None)
                    if callable(fn):
                        fn()
        except Exception as exc:
            _diag_exc(exc, 'qt/layout_panel.py.matrix_changed')
        apply_layout_to_project(self, True, _diag_exc)
        self._notify_layout_changed()

    def _on_strip_changed(self):
        try:
            apply_layout_to_project(self, False, _diag_exc)
        except Exception:
            return
        self._notify_layout_changed()

    def _on_preview_zoom_changed(self, value: int):
        try: zoom = int(value)
        except Exception: zoom = 8
        self._wiretap_log(f'[] zoom_changed -> {zoom}')
        widget = self._resolve_preview_widget()
        try:
            if widget is not None and hasattr(widget, 'set_zoom'):
                widget.set_zoom(zoom)
                if hasattr(widget, 'set_fit'):
                    widget.set_fit(False)
                widget.update()
        except Exception as exc:
            self._wiretap_log(f'[] zoom_apply_error: {exc}')

    def _on_preview_fit(self):
        self._wiretap_log('[] fit_clicked')
        widget = self._resolve_preview_widget()
        try:
            if widget is not None and hasattr(widget, 'set_fit'):
                widget.set_fit(True)
                widget.update()
        except Exception as exc:
            self._wiretap_log(f'[] fit_apply_error: {exc}')

    def _resolve_preview_widget(self):
        widget = getattr(self, '_preview_widget', None)
        if widget is not None:
            return widget
        ctrl = getattr(self, 'controller', None)
        widget = getattr(ctrl, 'surface_preview_widget', None) if ctrl is not None else None
        if widget is not None:
            self._preview_widget = widget
            return widget
        try:
            app = QtWidgets.QApplication.instance()
            if app is not None:
                for candidate in app.allWidgets():
                    if candidate.__class__.__name__ == 'SurfacePreviewWidget':
                        self._preview_widget = candidate
                        return candidate
        except Exception as exc:
            _diag_exc(exc, 'qt/layout_panel.py.resolve_preview_widget')
        return None
