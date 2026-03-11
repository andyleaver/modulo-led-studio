from __future__ import annotations

from types import MethodType

from app.project_canonical import apply_project_root
from app.eras.era_progression import (
    gates_for_project,
    get_active_era,
    get_unlocked,
    set_active,
    unlock_next,
)


def install_era_runtime_bridge(app_core) -> None:
    """Attach missing era helper methods to app_core at runtime."""

    def _project_dict(self):
        try:
            p = getattr(self, "project", None)
            if isinstance(p, dict):
                return p
        except Exception:
            pass
        return {}

    def _set_project(self, project):
        try:
            setattr(self, "project", project)
        except Exception:
            pass
        try:
            fn = getattr(self, "notify_project_changed", None)
            if callable(fn):
                fn()
        except Exception:
            pass
        try:
            fn = getattr(self, "mark_dirty", None)
            if callable(fn):
                fn()
        except Exception:
            pass

    if not hasattr(app_core, "get_era_id"):
        def get_era_id(self):
            try:
                return str(get_active_era(_project_dict(self)) or "era_1962_red")
            except Exception:
                return "era_1962_red"
        app_core.get_era_id = MethodType(get_era_id, app_core)

    if not hasattr(app_core, "set_era_id"):
        def set_era_id(self, era_id):
            try:
                p = dict(_project_dict(self) or {})
                set_active(p, str(era_id or ""))
                _set_project(self, p)
            except Exception:
                pass
        app_core.set_era_id = MethodType(set_era_id, app_core)

    if not hasattr(app_core, "get_unlocked_era_ids"):
        def get_unlocked_era_ids(self):
            try:
                return [str(x) for x in get_unlocked(_project_dict(self))]
            except Exception:
                return ["era_1962_red"]
        app_core.get_unlocked_era_ids = MethodType(get_unlocked_era_ids, app_core)

    if not hasattr(app_core, "get_next_era_id"):
        def get_next_era_id(self, current_era_id=None):
            try:
                p = dict(_project_dict(self) or {})
                nxt = unlock_next(p)
                _set_project(self, p)
                return nxt
            except Exception:
                return None
        app_core.get_next_era_id = MethodType(get_next_era_id, app_core)

    if not hasattr(app_core, "mark_era_done"):
        def mark_era_done(self, era_id, ok=True):
            try:
                p = dict(_project_dict(self) or {})
                st = dict(p.get("era_state") or {})
                done = dict(st.get("done_map") or {})
                done[str(era_id)] = bool(ok)
                st["done_map"] = done
                p, _validation, _changes = apply_project_root(p, "era_state", st)
                _set_project(self, p)
            except Exception:
                pass
        app_core.mark_era_done = MethodType(mark_era_done, app_core)

    if not hasattr(app_core, "get_era_done_map"):
        def get_era_done_map(self):
            try:
                p = _project_dict(self)
                st = dict(p.get("era_state") or {})
                raw = dict(st.get("done_map") or {})
                return {str(k): bool(v) for k, v in raw.items()}
            except Exception:
                return {}
        app_core.get_era_done_map = MethodType(get_era_done_map, app_core)

    if not hasattr(app_core, "get_era_gates"):
        def get_era_gates(self):
            try:
                return dict(gates_for_project(_project_dict(self)) or {})
            except Exception:
                return {}
        app_core.get_era_gates = MethodType(get_era_gates, app_core)

    if not hasattr(app_core, "is_era_complete"):
        def is_era_complete(self):
            try:
                p = _project_dict(self)
                st = dict(p.get("era_state") or {})
                return bool(st.get("completed", False))
            except Exception:
                return False
        app_core.is_era_complete = MethodType(is_era_complete, app_core)

    if not hasattr(app_core, "set_era_complete"):
        def set_era_complete(self, ok=True):
            try:
                p = dict(_project_dict(self) or {})
                st = dict(p.get("era_state") or {})
                st["completed"] = bool(ok)
                p, _validation, _changes = apply_project_root(p, "era_state", st)
                _set_project(self, p)
            except Exception:
                pass
        app_core.set_era_complete = MethodType(set_era_complete, app_core)
