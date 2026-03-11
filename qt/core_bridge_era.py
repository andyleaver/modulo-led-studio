from __future__ import annotations

from app.eras.era_state import (
    get_era_id as _get_era_id,
    set_era_id as _set_era_id,
    is_era_complete as _is_era_complete,
    set_era_complete as _set_era_complete,
    get_era_done_map as _get_era_done_map,
    get_unlocked_era_ids as _get_unlocked_era_ids,
    mark_era_done as _mark_era_done,
    get_next_era_id as _get_next_era_id,
)
from app.eras.era_history import get_era, get_studio_tools_for_era, get_modulo_era
from app.eras.era_templates import get_era_template_project
from app.project_canonical import apply_project_root


class CoreBridgeEraMixin:
    def get_era_id(self) -> str:
        try:
            return _get_era_id(self.project)
        except Exception:
            return "era_1962_red"

    def set_era_id(self, era_id: str):
        """Persist era_id into project.ui.

        During Era onboarding (era_complete == False), also apply the era template immediately
        so the user sees the era-accurate sandbox content for that era.
        """
        try:
            p = _set_era_id(self.project, str(era_id))
            ui = (p.get('ui') or {}) if isinstance(p, dict) else {}
            done = ui.get('era_done', {}) if isinstance(ui.get('era_done', {}), dict) else {}
            era_complete = bool(ui.get('era_complete', False))
            if not era_complete:
                # Apply the template for this era now (not only on first-run).
                tpl = get_era_template_project(str(era_id))
                if isinstance(tpl, dict) and tpl:
                    ui1 = (tpl.get('ui') or {}) if isinstance(tpl.get('ui'), dict) else {}
                    ui1['era_template_applied'] = True
                    ui1['era_done'] = dict(done)
                    tpl, _validation, _changes = apply_project_root(tpl, 'ui', ui1)
                    self.project = tpl
                    return
            # Otherwise, just set the era_id on the current project.
            self.project = p
        except Exception as e:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
            pass

    def get_era_done_map(self) -> dict:
        try:
            return dict(_get_era_done_map(self.project))
        except Exception:
            return {}

    def get_unlocked_era_ids(self) -> list:
        try:
            return list(_get_unlocked_era_ids(self.project))
        except Exception:
            return []

    def mark_era_done(self, era_id: str, done: bool = True):
        try:
            p = _mark_era_done(self.project, str(era_id), bool(done))
            self.set_project(p)
        except Exception:
            pass

    def get_next_era_id(self, era_id: str | None = None):
        try:
            return _get_next_era_id(self.project, era_id)
        except Exception:
            return None

    def get_era_gates(self) -> dict:
        """Return current era gates as a plain dict for Qt UI gating.

        Once era onboarding is completed, always expose the final Modulo era gates
        regardless of the currently remembered browsing/era id.
        """
        try:
            try:
                era = get_modulo_era() if bool(self.is_era_complete()) else get_era(self.get_era_id())
            except Exception:
                era = get_era(self.get_era_id())
            g = getattr(era, 'gates', None)
            if g is None:
                return {}
            # dataclass -> dict (minimal)
            return {
                'allowed_effects': list(getattr(g, 'allowed_effects', []) or []),
                'max_layers': int(getattr(g, 'max_layers', 1) or 1),
                'allow_operators': bool(getattr(g, 'allow_operators', False)),
                'allow_rules': bool(getattr(g, 'allow_rules', False)),
                'allow_audio': bool(getattr(g, 'allow_audio', False)),
                'allow_targets': bool(getattr(g, 'allow_targets', False)),
                'allow_export': bool(getattr(g, 'allow_export', False)),
                'allow_matrix': bool(getattr(g, 'allow_matrix', False)),
                'allow_addressable': bool(getattr(g, 'allow_addressable', False)),
                'allow_presets': bool(getattr(g, 'allow_presets', False)),
                'allow_full_modulo': bool(getattr(g, 'allow_full_modulo', False)),
                'control_model': str(getattr(g, 'control_model', 'full_modulo') or 'full_modulo'),
                'phase_kind': str(getattr(g, 'phase_kind', 'historical') or 'historical'),
                'stop_here_ok': bool(getattr(g, 'stop_here_ok', False)),
                'control_capabilities': list(getattr(g, 'control_capabilities', []) or []),
                'studio_tools': list(get_studio_tools_for_era(era)),
            }
        except Exception:
            return {}

    def is_era_complete(self) -> bool:
        """Return whether the user has completed the Era onboarding."""
        try:
            return bool(_is_era_complete(self.project))
        except Exception:
            return False

    def set_era_complete(self, complete: bool):
        """Persist era_complete into project.ui and rebuild."""
        try:
            p = _set_era_complete(self.project, bool(complete))
            self.project = p
        except Exception as e:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
            pass
