from __future__ import annotations

from qt.era_ui_gate import apply_ui_gates
from qt.tab_registry import apply_era_tab_gating
from .main_window_era import user_flag_path


class MainWindowModeMixin:
    def _studio_mode_path(self):
        return user_flag_path(self.app_core, 'studio_mode.txt')

    def _save_studio_mode(self, mode_name: str):
        try:
            path = self._studio_mode_path()
            if path is not None:
                path.write_text(f"{str(mode_name or '').strip()}\n", encoding='utf-8')
        except Exception:
            pass

    def _load_studio_mode(self):
        try:
            path = self._studio_mode_path()
            if path is not None and path.exists():
                return str(path.read_text(encoding='utf-8', errors='ignore') or '').strip()
        except Exception:
            pass
        return 'full_modulo'

    def _apply_studio_mode(self, mode_name: str):
        try:
            tabs = getattr(self, 'tabs', None)
            if tabs is None:
                return
            visible_labels = ['Surface', 'Layers', 'Behaviour', 'Inputs', 'Preview', 'Export']
            mode_lower = str(mode_name or '').strip().lower()
            if mode_lower == 'effect_picker':
                visible_labels = ['Surface', 'Layers', 'Preview', 'Export']
            for i in range(tabs.count()):
                label = str(tabs.tabText(i) or '')
                want = label in visible_labels
                try:
                    tabs.setTabVisible(i, bool(want))
                except Exception:
                    widget = tabs.widget(i)
                    if widget is not None:
                        widget.setVisible(bool(want))
            for i in range(tabs.count()):
                try:
                    ok = tabs.isTabVisible(i)
                except Exception:
                    widget = tabs.widget(i)
                    ok = bool(widget is not None and widget.isVisible())
                if ok:
                    tabs.setCurrentIndex(i)
                    break
            if hasattr(self, '_workflow_banner'):
                if mode_lower == 'effect_picker':
                    self._workflow_banner.setText('Workflow: Surface → Layers → Preview → Export')
                else:
                    self._workflow_banner.setText('Workflow: Surface → Layers → Behaviour → Inputs → Preview → Export')
            if hasattr(self, '_workflow_mode'):
                self._workflow_mode.setText('Mode: Effect Picker' if mode_lower == 'effect_picker' else 'Mode: Full Modulo')
            self._save_studio_mode(mode_lower or 'full_modulo')
        except Exception:
            pass


    def _on_layout_changed(self):
        """Route preview widgets by canonical surface kind.

        Strip projects render in the dedicated top strip preview. Cells projects render
        in the right-hand preview stack.
        """
        try:
            from app.project_model import get_surface_kind
            project = getattr(self.app_core, 'project', {}) or {}
            kind = str(get_surface_kind(project) or 'strip').strip().lower()
        except Exception:
            kind = 'strip'

        is_strip = (kind == 'strip')

        try:
            if getattr(self, 'strip_header', None) is not None:
                self.strip_header.setVisible(is_strip)
        except Exception:
            pass
        try:
            if getattr(self, 'strip_mini', None) is not None:
                self.strip_mini.setVisible(is_strip)
                self.strip_mini.update()
        except Exception:
            pass
        try:
            if getattr(self, 'preview_stack', None) is not None:
                # index 0 = matrix/cells preview, index 1 = no-preview placeholder
                self.preview_stack.setCurrentIndex(1 if is_strip else 0)
                self.preview_stack.setVisible(not is_strip)
        except Exception:
            pass
        try:
            if getattr(self, 'surface_preview_widget', None) is not None:
                self.surface_preview_widget.update()
        except Exception:
            pass

    def _toggle_diagnostics_console(self):
        try:
            console = getattr(self, '_diag_console', None)
            if console is None:
                return
            if console.isVisible():
                console.hide()
            else:
                console.show()
                try:
                    console.raise_()
                except Exception:
                    pass
        except Exception:
            pass

    def _preferred_studio_tab_index(self, gates: dict | None = None, focus_modulo: bool = False):
        try:
            gates = dict(gates or {})
            model = str((gates or {}).get('control_model') or '').strip().lower()
            if bool(focus_modulo) or bool(getattr(self.app_core, 'is_era_complete', lambda: False)()):
                preferred_tools = ['surface_layout', 'target_setup', 'layer_stack', 'effect_library', 'operators_panel', 'signal_routing', 'variables_panel', 'rules_editor', 'preset_browser', 'playlist', 'export_panel']
            elif model == 'effect_picker':
                preferred_tools = ['effect_library', 'surface_layout', 'target_setup', 'layer_stack', 'preset_browser', 'playlist', 'export_panel']
            else:
                preferred_tools = ['surface_layout', 'target_setup', 'layer_stack', 'effect_library', 'operators_panel', 'signal_routing', 'variables_panel', 'rules_editor', 'preset_browser', 'playlist', 'export_panel']
            specs = list(getattr(self, '_era_tab_specs', []) or [])
            allowed = set((gates or {}).get('studio_tools') or [])
            for tool in preferred_tools:
                if allowed and tool not in allowed:
                    continue
                for spec in specs:
                    idx = int(spec.get('index', -1))
                    if idx >= 0 and str(spec.get('tool') or '').strip() == tool:
                        return idx
            for spec in specs:
                idx = int(spec.get('index', -1))
                if idx < 0:
                    continue
                try:
                    if not hasattr(self.tabs, 'isTabVisible') or self.tabs.isTabVisible(idx):
                        return idx
                except Exception:
                    return idx
            return 0
        except Exception:
            return 0

    def refresh_era_ui(self, focus_modulo: bool = False):
        try:
            apply_era_tab_gating(self)
            apply_ui_gates(self)
            if bool(getattr(self.app_core, 'is_era_complete', lambda: False)()):
                try:
                    from qt.tab_registry import _set_tab_visible_safe
                    for spec in list(getattr(self, '_era_tab_specs', []) or []):
                        idx = int(spec.get('index', -1))
                        if idx >= 0:
                            _set_tab_visible_safe(self.tabs, idx, True)
                except Exception:
                    pass
        except Exception:
            pass
        for name in ['era_panel', 'layout_panel', 'layers_tab', 'effects_tab', 'presets_tab', 'playlist_tab', 'operators_tab', 'rules_tab', 'signals_tab', 'targets_tab', 'variables_tab', 'export_tab', 'diagnostics_tab']:
            try:
                panel = getattr(self, name, None)
                if panel is None:
                    continue
                if hasattr(panel, 'sync_from_project'):
                    panel.sync_from_project()
                elif hasattr(panel, 'refresh'):
                    panel.refresh()
            except Exception:
                pass
        try:
            if hasattr(self, 'tabs'):
                gates = {}
                try:
                    fn = getattr(self.app_core, 'get_era_gates', None)
                    gates = fn() if callable(fn) else {}
                except Exception:
                    gates = {}
                stop_here_ok = bool((gates or {}).get('stop_here_ok', False))
                if bool(getattr(self.app_core, 'is_era_complete', lambda: False)()) or bool(focus_modulo) or stop_here_ok:
                    target_idx = self._preferred_studio_tab_index(gates=gates, focus_modulo=bool(focus_modulo))
                else:
                    target_idx = 0
                self.tabs.setCurrentIndex(int(target_idx))
            if hasattr(self, 'surface_preview_widget') and self.surface_preview_widget is not None:
                self.surface_preview_widget.update()
        except Exception:
            pass

    def post_startup_init(self):
        try:
            if getattr(self, '_did_post_startup', False):
                return
            self._did_post_startup = True
        except Exception:
            pass
        try:
            fn = getattr(self.app_core, '_rebuild_full_preview_engine', None)
            if callable(fn):
                fn()
        except Exception:
            pass
        try:
            self._on_layout_changed()
        except Exception:
            pass
        try:
            apply_era_tab_gating(self)
        except Exception:
            pass
        panel_refs = [
            getattr(getattr(self, 'controls', None), 'layers_panel', None),
            getattr(getattr(self, 'controls', None), 'operators_panel', None),
            getattr(getattr(self, 'controls', None), 'zones_panel', None),
            getattr(getattr(self, 'controls', None), 'export_panel', None),
        ]
        for panel in panel_refs:
            try:
                if panel is None:
                    continue
                if hasattr(panel, 'sync_from_project'):
                    panel.sync_from_project()
            except Exception:
                pass
