from __future__ import annotations

from app.project_model import get_surface_spec


class CoreBridgeUiStateMixin:
    @property
    def target_mask(self) -> str | None:
        try:
            r = self.resolve_canonical("project.ui.target_mask", default=None)
            return None if r.value in (None, '') else str(r.value)
        except Exception:
            return None

    @target_mask.setter
    def target_mask(self, key: str | None):
        try:
            pm = getattr(self, 'pm', None)
            if pm is not None and hasattr(pm, 'guarded_set_target_mask'):
                if bool(pm.guarded_set_target_mask(key)):
                    return
            from runtime.resolver import set_address
            p2, did = set_address(project=self.project or {}, address="project.ui.target_mask", value=(None if key in (None, '') else str(key)))
            if did:
                self.project = p2
        except Exception as e:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge_ui_state.py"})
            pass

    def _on_target_mask_changed(self, _idx: int = 0):
        try:
            sender = self.sender()
            key = sender.currentData() if sender is not None and hasattr(sender, 'currentData') else None
            self.app_core.target_mask = None if key in (None, '') else str(key)
        except Exception:
            pass

    def _clear_pixel_selection(self):
        try:
            self.app_core.set_selection_indices([])
            if hasattr(self, 'surface_preview_widget') and self.surface_preview_widget is not None:
                self.surface_preview_widget.update()
        except Exception:
            pass

    def add_composed_mask(self, key: str, op: str, a, b) -> None:
        from app.masks_api import create_composed_mask

        p = self.project or {}
        n = None
        try:
            spec = get_surface_spec(p)
            n = int(getattr(spec, "count", 0) or 0) or None
        except Exception:
            n = None

        p2 = create_composed_mask(p, key, op, a, b, validate=True, n=n)
        self.project = p2

    def get_export_target_id(self) -> str:
        try:
            p = self.project or {}
            ex = p.get("export") or {}
            if isinstance(ex, dict):
                tid = ex.get("target_id")
                if tid:
                    return str(tid)
        except Exception as e:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge_ui_state.py"})
            pass
        return str(self._export_target_id)

    def set_export_target_id(self, tid: str):
        try:
            self._export_target_id = str(tid)
        except Exception as e:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge_ui_state.py"})
            pass

    def get_selection_indices(self) -> list[int]:
        try:
            return list(self._selection_indices or [])
        except Exception:
            return []

    def set_selection_indices(self, indices):
        try:
            out: list[int] = []
            for x in (indices or []):
                try:
                    out.append(int(x))
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge_ui_state.py"})
                    pass
            self._selection_indices = sorted(set(out))
        except Exception:
            self._selection_indices = []
