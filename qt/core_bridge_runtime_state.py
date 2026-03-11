from __future__ import annotations

from runtime.variables import get_variables_state, ensure_variables
from runtime.canonical_addr import parse_bool


class CoreBridgeRuntimeStateMixin:
    def get_rules_last_fired_summary(self) -> str:
        """Return a human-readable last-fired summary for Phase 6 rules."""
        try:
            ids = list(getattr(self, "_rules_last_fired_ids", []) or [])
        except Exception:
            ids = []
        if not ids:
            return "Last fired: (none)"
        # Map ids -> names if possible
        try:
            p = self.project
            rules = list((p.get("rules") or []))
            id_to_name = {}
            for r in rules:
                if isinstance(r, dict) and r.get("id"):
                    id_to_name[str(r.get("id"))] = str(r.get("name") or r.get("id"))
            parts = [id_to_name.get(str(i), str(i)) for i in ids]
        except Exception:
            parts = [str(i) for i in ids]
        return "Last fired: " + ", ".join(parts)

    def get_signal_snapshot(self) -> dict:
        """Return a dict snapshot of current signal values (best-effort)."""
        try:
            snap = self.signal_bus.snapshot()
            return dict(snap.signals or {})
        except Exception:
            return {}

    def variables_revision(self) -> int:
        """Monotonic revision counter for runtime variables changes."""
        try:
            return int(getattr(self, "_variables_rev", 0))
        except Exception:
            return 0

    def variables_runtime_dirty(self) -> bool:
        """True if runtime variables differ from project defaults (or have been touched)."""
        try:
            return bool(getattr(self, "_variables_runtime_dirty", False))
        except Exception:
            return False

    def get_runtime_variables_state(self) -> dict:
        """Return a shallow copy of runtime variables state."""
        try:
            vs = getattr(self, "_variables_state", None)
            if isinstance(vs, dict):
                return {"number": dict(vs.get("number") or {}), "toggle": dict(vs.get("toggle") or {})}
        except Exception as e:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
            pass
        return {"number": {}, "toggle": {}}

    def _sync_runtime_variables_with_project(self, project: dict, *, overwrite_values: bool) -> None:
        """Ensure runtime variables key-set matches project variables."""
        try:
            p_state = get_variables_state(project)
            if not isinstance(p_state, dict):
                p_state = {"number": {}, "toggle": {}}
            r_state = self.get_runtime_variables_state()
            out_num = dict(r_state.get("number") or {})
            out_tog = dict(r_state.get("toggle") or {})
            p_num = dict(p_state.get("number") or {})
            p_tog = dict(p_state.get("toggle") or {})

            if overwrite_values:
                out_num = dict(p_num)
                out_tog = dict(p_tog)
            else:
                for k, v in p_num.items():
                    if k not in out_num:
                        out_num[k] = v
                for k, v in p_tog.items():
                    if k not in out_tog:
                        out_tog[k] = v
                for k in list(out_num.keys()):
                    if k not in p_num:
                        out_num.pop(k, None)
                for k in list(out_tog.keys()):
                    if k not in p_tog:
                        out_tog.pop(k, None)

            self._variables_state = {"number": out_num, "toggle": out_tog}
            self._variables_rev = int(getattr(self, "_variables_rev", 0)) + 1
        except Exception as e:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
            pass

    def set_runtime_variable(self, kind: str, name: str, value) -> None:
        """Set a runtime variable value (does not persist to project unless committed)."""
        try:
            kind = str(kind or "").strip().lower()
            name = str(name or "").strip()
            if kind not in ("number", "toggle") or not name:
                return

            vs = self.get_runtime_variables_state()
            if kind == "number":
                try:
                    vs["number"][name] = float(value)
                except Exception:
                    return
            else:
                b = parse_bool(value)
                vs["toggle"][name] = bool(b) if b is not None else bool(value)

            self._variables_state = vs
            self._variables_runtime_dirty = True
            self._variables_rev = int(getattr(self, "_variables_rev", 0)) + 1
        except Exception as e:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
            pass

    def commit_runtime_variables_to_project(self) -> None:
        """Persist runtime variables into project['variables'] (authoring action)."""
        try:
            p = self.project or {}
            p2, _ = ensure_variables(p)
            vs = self.get_runtime_variables_state()
            v = dict(p2.get("variables") or {})
            v["number"] = dict(vs.get("number") or {})
            v["toggle"] = dict(vs.get("toggle") or {})
            p3, _snap, _changes = apply_project_root(p2, "variables", v)
            self._variables_runtime_dirty = False
            self.project = p3
            self._variables_rev = int(getattr(self, "_variables_rev", 0)) + 1
        except Exception as e:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
            pass

    def revert_runtime_variables_from_project(self) -> None:
        """Reset runtime variables from project defaults."""
        try:
            self._sync_runtime_variables_with_project(self.project or {}, overwrite_values=True)
            self._variables_runtime_dirty = False
            try:
                self.rebuild_preview(reason="variables.revert")
            except Exception as e:
                from runtime.diagnostics import GLOBAL_DIAGS
                GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                pass
        except Exception as e:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
            pass

    def _diagnostics_tick_audio(self):
        """Advance AudioSim slightly so health reports show non-zero values."""
        a = getattr(self, "preview_audio", None)
        if a is None:
            return
        if a.__class__.__name__ != "AudioSim":
            return
        for _ in range(10):
            a.step(0.05)
