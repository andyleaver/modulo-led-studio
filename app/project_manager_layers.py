from __future__ import annotations

import copy

from app.project_apply import apply_project_root
from app.project_manager_diagnostics import project_manager_diag_exc
from runtime.canonical_addr import canonicalize_layer_param_name
from runtime.resolver import set_address

_pm_diag_exc = project_manager_diag_exc

# ---- guarded layer helpers (single source of truth) ----
def is_layer_locked(self, idx: int) -> bool:
    try:
        layers = (self.project.get("layers") or [])
        if 0 <= idx < len(layers):
            return bool((layers[idx] or {}).get("locked", False))
    except Exception as e:
        _pm_diag_exc(e, "is_layer_locked")
    return False

def guarded_update_layer(self, idx: int, updater, *, reason: str = "modify"):
    """Apply updater(layer_dict) if layer is not locked. Returns True if applied."""
    try:
        if self.is_layer_locked(idx):
            return False
        layers = (self.project.get("layers") or [])
        if not (0 <= idx < len(layers)):
            return False
        layer = layers[idx] or {}
        updater(layer)
        layers[idx] = layer
        project, _snap, _changes = apply_project_root(self.project, "layers", layers)
        self.project = project
        self.dirty = True
        self._notify()
        return True
    except Exception as e:
        _pm_diag_exc(e, "return_false")
        return False

def guarded_set_address(self, address: str, value) -> bool:
    """Canonical write path for first-class project/runtime doors."""
    try:
        pnew, changed = set_address(project=self.project, address=str(address or ""), value=value)
        if not changed:
            return False
        self.project = pnew
        self.dirty = True
        self._notify()
        return True
    except Exception as e:
        _pm_diag_exc(e, "guarded_set_address", {"address": str(address or "")})
        return False

def guarded_set_layer_param(self, idx: int, name: str, value) -> bool:
    """Set a layer destination using the canonical path when applicable.

    Canonical destinations (layer fields / project.postfx / operator overrides)
    must NOT be written into params, because that recreates split paths.
    Unknown names still route to effect params for now.
    """
    try:
        tgt = canonicalize_layer_param_name(str(name or ""))
    except Exception as e:
        _pm_diag_exc(e, "guarded_set_layer_param.canonicalize", {"name": str(name or "")})
        tgt = None

    if tgt is not None:
        if tgt.scope == "layer_field":
            return self.guarded_set_address(f"layers[{int(idx)}].{tgt.key}", value)
        if tgt.scope == "project_postfx":
            return self.guarded_set_address(f"project.postfx.{tgt.key}", value)
        if tgt.scope == "operator_param":
            return self.guarded_set_address(f"layers[{int(idx)}]._op_overrides.{tgt.key}", value)

    def _u(layer):
        params = dict(layer.get("params") or {})
        params[str(name)] = value
        layer["params"] = params
    return self.guarded_update_layer(idx, _u, reason="set_param")

def apply_rule_layer_mutations(self, mutations, *, active_layer: int | None = None) -> bool:
    """Apply Rules layer_param mutations through the canonical project manager path.

    This keeps rule-driven writes on the same first-class write doors used by the UI
    instead of re-implementing canonical routing inside preview glue.
    """
    try:
        if not mutations:
            return False
        pnow = self.project
        layers = list((pnow.get("layers") or []))
        changed = False
        for item in list(mutations):
            try:
                li, param, val = item
            except Exception:
                continue
            try:
                li = int(li)
            except Exception:
                li = 0
            if li == -1:
                try:
                    if active_layer is not None:
                        li = int(active_layer)
                    else:
                        ui = pnow.get("ui", {}) if isinstance(pnow, dict) else {}
                        li = int((ui.get("selected_layer", -1) if isinstance(ui, dict) else -1) or -1)
                except Exception:
                    li = -1
            if li < 0 or li >= len(layers):
                continue
            pname = str(param or "")
            if not pname:
                continue
            tgt = None
            try:
                tgt = canonicalize_layer_param_name(pname)
            except Exception as e:
                _pm_diag_exc(e, "apply_rule_layer_mutations.canonicalize", {"name": pname})
                tgt = None
            if tgt is not None:
                if tgt.scope == "layer_field":
                    addr = f"layers[{li}].{tgt.key}"
                elif tgt.scope == "project_postfx":
                    addr = f"project.postfx.{tgt.key}"
                elif tgt.scope == "operator_param":
                    addr = f"layers[{li}]._op_overrides.{tgt.key}"
                else:
                    addr = None
                if addr:
                    pnew, did = set_address(project=pnow, address=addr, value=val)
                    if did:
                        pnow = pnew
                        layers = list((pnow.get("layers") or []))
                        changed = True
                    continue
            L = dict(layers[li] or {})
            params = dict(L.get("params") or {}) if isinstance(L.get("params"), dict) else {}
            try:
                params[pname] = float(val) if isinstance(val, (int, float)) else val
            except Exception:
                params[pname] = val
            if L.get("params") == params:
                continue
            L["params"] = params
            layers[li] = L
            pnow, _snap, _changes = apply_project_root(pnow, "layers", layers)
            changed = True
        if not changed:
            return False
        self.project = pnow
        self.dirty = True
        self._notify()
        return True
    except Exception as e:
        _pm_diag_exc(e, "apply_rule_layer_mutations")
        return False

def guarded_set_layer_effect(self, idx: int, effect_key: str, params: dict | None = None) -> bool:
    def _u(layer):
        # Canonical layer identity lives on behavior only. Remove any legacy effect shadow.
        layer["behavior"] = effect_key
        layer.pop("effect", None)
        if params is not None:
            layer["params"] = dict(params)
    return self.guarded_update_layer(idx, _u, reason="set_effect")

def guarded_toggle_layer_enabled(self, idx: int) -> bool:
    current_enabled = True
    try:
        from runtime.resolver import resolve_layer_field
        current_enabled = bool(resolve_layer_field(project=self.project, layer_index=int(idx), field="enabled", runtime=None, default=True).value)
    except Exception:
        current_enabled = True
    def _u(layer):
        layer["enabled"] = not bool(current_enabled)
    return self.guarded_update_layer(idx, _u, reason="toggle_enabled")

def guarded_remove_layer(self, idx: int) -> bool:
    try:
        if self.is_layer_locked(idx):
            return False
        layers = (self.project.get("layers") or [])
        if not (0 <= idx < len(layers)):
            return False
        layers.pop(idx)
        pnow, _snap, _changes = apply_project_root(self.project, "layers", layers)
        # clear selection if it pointed past end using canonical UI address
        sel = self.project.get("ui", {}).get("selected_layer", None)
        try:
            if sel is not None and int(sel) >= len(layers):
                p2, did = set_address(project=pnow, address="project.ui.selected_layer", value=(max(0, len(layers)-1) if layers else -1))
                if did:
                    pnow = p2
        except Exception as e:
            _pm_diag_exc(e, "guarded_remove_layer_selection_fix")
        self.project = pnow
        self.dirty = True
        self._notify()
        return True
    except Exception as e:
        _pm_diag_exc(e, "return_false")
        return False

def guarded_move_layer(self, idx: int, delta: int) -> bool:
    try:
        if self.is_layer_locked(idx):
            return False
        layers = (self.project.get("layers") or [])
        j = idx + int(delta)
        if not (0 <= idx < len(layers)) or not (0 <= j < len(layers)):
            return False
        layers[idx], layers[j] = layers[j], layers[idx]
        project, _snap, _changes = apply_project_root(self.project, "layers", layers)
        self.project = project
        self.dirty = True
        self._notify()
        return True
    except Exception as e:
        _pm_diag_exc(e, "return_false")
        return False

def guarded_add_layer(self, layer_dict: dict, *, idx: int | None = None) -> bool:
    """Insert new layer. If idx is provided, insertion happens at idx; if that slot is locked, returns False."""
    try:
        layers = list((self.project.get("layers") or []))
        insert_at: int
        if idx is None:
            insert_at = len(layers)
            layers.append(dict(layer_dict))
        else:
            idx = int(idx)
            if 0 <= idx < len(layers) and self.is_layer_locked(idx):
                return False
            if idx < 0:
                idx = 0
            if idx > len(layers):
                idx = len(layers)
            insert_at = idx
            layers.insert(insert_at, dict(layer_dict))
        project, _snap, _changes = apply_project_root(self.project, "layers", layers)
        self.project = project
        try:
            p2, did = set_address(project=self.project, address="project.ui.selected_layer", value=int(insert_at if layers else -1))
            if did:
                self.project = p2
        except Exception as e:
            _pm_diag_exc(e, "guarded_add_layer_selection_fix")
        self.dirty = True
        self._notify()
        return True
    except Exception as e:
        _pm_diag_exc(e, "return_false")
        return False

def guarded_set_selected_layer(self, idx: int) -> bool:
    """Persist the selected layer through the canonical project.ui.selected_layer address."""
    try:
        layers = (self.project.get("layers") or []) if isinstance(self.project, dict) else []
        if not isinstance(layers, list):
            layers = []
        if layers:
            idx = max(0, min(int(idx), len(layers) - 1))
        else:
            idx = -1
        p2, did = set_address(project=self.project, address="project.ui.selected_layer", value=int(idx))
        if not did:
            return False
        self.project = p2
        self.dirty = True
        self._notify()
        return True
    except Exception as e:
        _pm_diag_exc(e, "guarded_set_selected_layer")
        return False

def guarded_set_target_mask(self, key: str | None) -> bool:
    """Persist the global target mask through canonical project.ui.target_mask."""
    try:
        value = None if key in (None, '') else str(key)
        p2, did = set_address(project=self.project, address="project.ui.target_mask", value=value)
        if not did:
            return False
        self.project = p2
        self.dirty = True
        self._notify()
        return True
    except Exception as e:
        _pm_diag_exc(e, "guarded_set_target_mask")
        return False

def guarded_duplicate_layer(self, idx: int) -> bool:
    """Duplicate a layer and move canonical selection to the copy."""
    try:
        layers = (self.project.get("layers") or []) if isinstance(self.project, dict) else []
        if not isinstance(layers, list) or not (0 <= int(idx) < len(layers)):
            return False
        clone = copy.deepcopy(layers[int(idx)])
        clone["name"] = (clone.get("name") or "Layer") + " (copy)"
        if not self.guarded_add_layer(clone, idx=int(idx) + 1):
            return False
        try:
            self.guarded_set_selected_layer(int(idx) + 1)
        except Exception:
            pass
        return True
    except Exception as e:
        _pm_diag_exc(e, "guarded_duplicate_layer")
        return False

def guarded_fix_visible(self, idx: int, visible_mask: list[bool]) -> bool:
    def _u(layer):
        layer["visible"] = list(bool(x) for x in visible_mask)
    return self.guarded_update_layer(idx, _u, reason="fix_visible")


def bind_project_manager_layer_methods(project_manager_cls) -> None:
    """Attach guarded layer-edit methods to ProjectManager."""
    project_manager_cls.is_layer_locked = is_layer_locked
    project_manager_cls.guarded_update_layer = guarded_update_layer
    project_manager_cls.guarded_set_address = guarded_set_address
    project_manager_cls.guarded_set_layer_param = guarded_set_layer_param
    project_manager_cls.apply_rule_layer_mutations = apply_rule_layer_mutations
    project_manager_cls.guarded_set_layer_effect = guarded_set_layer_effect
    project_manager_cls.guarded_toggle_layer_enabled = guarded_toggle_layer_enabled
    project_manager_cls.guarded_remove_layer = guarded_remove_layer
    project_manager_cls.guarded_move_layer = guarded_move_layer
    project_manager_cls.guarded_add_layer = guarded_add_layer
    project_manager_cls.guarded_set_selected_layer = guarded_set_selected_layer
    project_manager_cls.guarded_set_target_mask = guarded_set_target_mask
    project_manager_cls.guarded_duplicate_layer = guarded_duplicate_layer
    project_manager_cls.guarded_fix_visible = guarded_fix_visible
