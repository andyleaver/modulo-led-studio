from __future__ import annotations

from app.eras.era_enforce import EraViolation
from app.project_canonical import finalize_project_dict
from app.project_model import get_surface_snapshot, get_surface_spec
from runtime.canonical_addr import canonicalize_layer_param_name, clamp01, parse_bool, normalize_blend_mode
from runtime.resolver import resolve_address
from qt.core_bridge_flags import ERA_ENFORCEMENT_DISABLED


class CoreBridgeProjectMixin:
    @property
    def project(self) -> dict:
        try:
            p = getattr(self, '_project', None)
            return p if isinstance(p, dict) else {}
        except Exception:
            return {}

    @property
    def last_validation(self):
        try:
            return self._last_validation
        except Exception:
            return {'ok': True, 'errors': [], 'warnings': []}

    def project_revision(self) -> int:
        try:
            return int(getattr(self, '_project_rev', 0))
        except Exception:
            return 0

    def set_project(self, value):
        """Canonical compatibility setter used across Qt bridge mixins/tests."""
        self.project = value
        return self.project

    @project.setter
    def project(self, value):
        p = value if isinstance(value, dict) else {}

        try:
            p, snap, _changes = finalize_project_dict(
                p,
                sanitize_for_era=(not ERA_ENFORCEMENT_DISABLED),
                enforce_era=(not ERA_ENFORCEMENT_DISABLED),
                validate=True,
            )
        except EraViolation as ev:
            self._last_validation = {'ok': False, 'errors': [str(ev)], 'warnings': []}
            raise

        try:
            dirty = bool(getattr(self, "_variables_runtime_dirty", False))
            self._sync_runtime_variables_with_project(p, overwrite_values=(not dirty))
        except Exception as e:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge_project.py"})
            pass

        self._last_validation = snap if isinstance(snap, dict) else {'ok': True, 'errors': [], 'warnings': []}
        self._project = p

        try:
            self._project_rev = int(getattr(self, '_project_rev', 0)) + 1
        except Exception:
            self._project_rev = 1

        try:
            if hasattr(self, 'pm') and self.pm is not None and hasattr(self.pm, 'set'):
                self.pm.set(p)
        except Exception as e:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge_project.py"})
            pass
        try:
            self.rebuild_preview(reason="project.setter")
        except Exception:
            pass

    def resolve_canonical(self, address: str, default=None):
        try:
            return resolve_address(project=self.project or {}, address=str(address), default=default)
        except Exception:
            class _Fallback:
                def __init__(self, value, source='error'):
                    self.value = value
                    self.source = source
            return _Fallback(default)

    def resolve_layer_canonical(self, layer_index: int, field: str, default=None):
        try:
            from runtime.resolver import resolve_layer_field
            return resolve_layer_field(project=self.project or {}, layer_index=int(layer_index), field=str(field or ""), runtime=None, default=default)
        except Exception:
            from types import SimpleNamespace
            return SimpleNamespace(value=default, source='default')

    def get_selected_layer(self) -> int:
        try:
            r = self.resolve_canonical("project.ui.selected_layer", default=-1)
            return int(r.value if r.value is not None else -1)
        except Exception:
            return -1
