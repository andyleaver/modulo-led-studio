from __future__ import annotations
from app.project_canonical import apply_project_roots
from app.project_model import get_surface_snapshot, build_surface_dict

from qt.diagnostics_console_audit_waits import DiagnosticsConsoleAuditWaitsMixin
from qt.diagnostics_console_audit_state import DiagnosticsConsoleAuditStateMixin


def _legacy_layer_param_mirror_keys() -> tuple[str, ...]:
    return (
        "layer_enabled",
        "layer_opacity",
        "layer_blend_mode",
        "layer_order",
    )


class DiagnosticsConsoleAuditCoreMixin(
    DiagnosticsConsoleAuditWaitsMixin,
    DiagnosticsConsoleAuditStateMixin,
):
    def _run_composition_door_suite_audit(self) -> tuple[bool, dict]:
        """Atomic composition doors (audit verdict).
        This is the canonical atomic proof used by FULL AUDIT. It must not depend on optional UI-only helpers.
        """
        try:
            # Preferred: dedicated checker if present.
            if hasattr(self, "_composition_suite_run_and_check") and callable(getattr(self, "_composition_suite_run_and_check")):
                return getattr(self, "_composition_suite_run_and_check")()

            # Back-compat: newer alias name if present.
            if hasattr(self, "_run_composition_door_suite_atomic_check") and callable(getattr(self, "_run_composition_door_suite_atomic_check")):
                return getattr(self, "_run_composition_door_suite_atomic_check")()

            # Last-resort: inline atomic suite (keeps FULL AUDIT runnable even if helpers were refactored).
            # Uses the same rule ids / expectations as the composition audit suite.
            return self._run_composition_door_suite_inline_audit()
        except Exception as e:
            return False, {"summary": f"Exception: {e}"}

    def _run_composition_door_suite_inline_audit(self) -> tuple[bool, dict]:
        """Inline atomic composition suite (enabled/blend/order/postfx)."""
        # If the dedicated checker exists, prefer it.
        try:
            self._audit_force_heartbeat()
        except Exception:
            pass
        # Reuse the existing suite builder if present; otherwise fail clearly.
        builder = getattr(self, "_build_composition_door_suite_project", None)
        if not callable(builder):
            return False, {"summary": "Missing atomic suite builder (_build_composition_door_suite_project)"}
        try:
            proj = builder()
        except Exception as e:
            return False, {"summary": f"Exception building atomic suite project: {e}"}

        # Run the suite and verify by waiting for BOTH: (a) rule fired, (b) state propagated (project+preview), then sample frame.
        runner = getattr(self, "_composition_suite_exec_steps", None)
        if not callable(runner):
            return False, {"summary": "Missing atomic suite executor (_composition_suite_exec_steps)"}
        try:
            return runner(proj)
        except Exception as e:
            return False, {"summary": f"Exception executing atomic suite: {e}"}

    def _run_coupled_composition_suite_audit(self) -> tuple[bool, dict]:
        """Coupled suite: enabled×blend×opacity + same-field conflict + temporal postfx coherency."""
        try:
            ok, details = self._coupled_suite_run_and_check()
            return ok, details
        except Exception as e:
            return False, {"summary": f"Exception: {e}"}

    def _audit_inject_project(self, *, layers: list, rules: list, postfx: dict | None = None) -> None:
        core = self.app_core
        p0 = dict(getattr(core, "project", {}) or {})
        surface = get_surface_snapshot(p0)
        if not isinstance(surface, dict) or not surface:
            surface = build_surface_dict(kind='strip', count=144)

        # Normalize harness layers to canonical project schema expected by models.io.load_project:
        #   layer['behavior'] + layer['params']
        # Diagnostics should author canonical-only layers so audit evidence is not polluted
        # by legacy layer identity shadows.
        norm_layers = []
        for i, L0 in enumerate(list(layers or [])):
            L = dict(L0 or {}) if isinstance(L0, dict) else {}
            # Drop any legacy shadow key outright; diagnostics fixtures must stay canonical-only.
            L.pop("effect", None)
            # Ensure params is always a real dict on authored harness layers.
            if not isinstance(L.get("params"), dict):
                L["params"] = {}
            # Ensure order is stable if omitted.
            if "order" not in L:
                L["order"] = int(i)
            norm_layers.append(L)

        p = dict(p0)
        ui = dict(p.get("ui") or {})
        ui["selected_layer"] = 1
        ui["era_id"] = str((ui or {}).get("era_id") or "era_now")
        variables = dict(p.get("variables") or {"number": {}, "toggle": {}})
        # Diagnostics must inject a clean canonical postfx block by default.
        # Otherwise a previous suite's trail/bleed state can leak into the next
        # injected project through p0 and create false mixed-frame failures.
        pfx = dict(postfx) if postfx is not None else {"trail_amount": 0.0, "bleed_amount": 0.0, "bleed_radius": 2.0}

        # Audit-only: stamp a unique runtime cache key into postfx so PreviewEngine can
        # persist temporal PostFX history across rebuilds *within* this injected project,
        # without leaking history across separate injections.
        try:
            seq = int(getattr(self, "_audit_inject_seq", 0) or 0) + 1
        except Exception:
            seq = 1
        self._audit_inject_seq = seq
        try:
            pfx = dict(pfx)
            pfx["_rt_cache_key"] = f"audit_inject_{seq:06d}"
        except Exception:
            pass

        p2, _validation, _changes = apply_project_roots(
            p,
            {
                "surface": surface,
                "layers": norm_layers,
                "ui": ui,
                "rules": rules,
                "variables": variables,
                "postfx": pfx,
            },
        )

        core.project = p2
        core.project_dirty = True
        # Keep ProjectManager and app_core on the same injected project so later
        # guarded_set_address() mutations operate on the current audit project rather
        # than an older stale pm.project snapshot.
        try:
            pm = getattr(core, "pm", None)
            if pm is not None:
                pm.project = dict(p2)
                try:
                    pm.dirty = True
                except Exception:
                    pass
                try:
                    pm._notify()
                except Exception:
                    pass
        except Exception:
            pass
        self._audit_safe_rebuild("audit_inject")

    def _audit_rule_tick(self, id_: str, cond_signal: str, op: str, value: float, action: dict) -> dict:
        return {
            "id": id_,
            "enabled": True,
            "name": id_,
            "trigger": "tick",
            "trigger_mode": "all",
            "conditions": [{"signal": cond_signal, "op": op, "value": value}],
            "action": action,
        }

    def _audit_action_layer_param(self, layer: int, param: str, value):
        return {
            "kind": "set_layer_param",
            "layer": int(layer),
            "param": str(param),
            "expr": {"src": "const", "const": value},
            "conflict": "last",
        }
