from __future__ import annotations

from typing import Any, Dict, List, Tuple

from runtime.extensions import get_rule_action

from .rules_support import _diag_exc, _eval_expr, _resolve_bool, _resolve_num, _to_float


def stage_rule_action(rule: dict, *, signals: Dict[str, Any], v2: Dict[str, Any], prev_state: Dict[str, Any], errors: List[str], allow_layer_param_mutation: bool = True):
    rr = rule if isinstance(rule, dict) else {}
    rid = str(rr.get("id", "") or "")
    act = rr.get("action") if isinstance(rr.get("action"), dict) else {}
    kind = str((act or {}).get("kind", "") or "")
    try:
        if kind in ("set_var", "add_var"):
            vkind = str((act or {}).get("var_kind", "number") or "number")
            vname = str((act or {}).get("var", "") or "")
            if not vname:
                errors.append(f"rule {rid}: missing var name")
                return None, False
            if vkind not in ("number", "toggle"):
                errors.append(f"rule {rid}: invalid var_kind '{vkind}'")
                return None, False
            expr = (act or {}).get("expr") if isinstance((act or {}).get("expr"), dict) else {}
            val = _eval_expr(expr, signals)
            conflict = str((act or {}).get("conflict", "last") or "last")
            return {
                "kind": kind,
                "var_kind": vkind,
                "var": vname,
                "value": val,
                "conflict": conflict,
            }, True

        if kind == "flip_toggle":
            vname = str((act or {}).get("var", "") or "")
            if not vname:
                errors.append(f"rule {rid}: missing var name")
                return None, False
            return {"kind": "flip_toggle", "var_kind": "toggle", "var": vname}, True

        if kind == "set_layer_param":
            if not allow_layer_param_mutation:
                errors.append(f"rule {rid}: layer param actions disabled")
                return None, False
            try:
                li = int((act or {}).get("layer", 0) or 0)
            except Exception:
                _diag_exc(Exception("parse_action_layer_index"), stage="parse_action_layer_index", rule_id=rid, details={"value": repr((act or {}).get("layer"))})
                li = 0
            param = str((act or {}).get("param", "") or "")
            if not param:
                errors.append(f"rule {rid}: missing layer param")
                return None, False
            expr = (act or {}).get("expr") if isinstance((act or {}).get("expr"), dict) else {}
            val = _eval_expr(expr, signals)
            conflict = str((act or {}).get("conflict", "last") or "last")
            return {
                "kind": "set_layer_param",
                "layer": li,
                "param": param,
                "value": val,
                "conflict": conflict,
            }, True

        fn = get_rule_action(kind)
        if fn is not None:
            try:
                out = fn({
                    "project": None,
                    "signals": signals,
                    "variables": v2,
                    "prev_state": prev_state,
                    "action": act,
                    "rule_id": rid,
                })
                if isinstance(out, dict):
                    vv = out.get("variables")
                    if isinstance(vv, dict):
                        for k0 in ("number", "toggle"):
                            if isinstance(vv.get(k0), dict):
                                v2[k0].update(vv.get(k0) or {})
                    pm = out.get("project_mutations")
                    ee = out.get("errors")
                    if isinstance(ee, list):
                        errors.extend([str(x) for x in ee if x is not None])
                    return {"kind": "__extension__", "project_mutations": pm if isinstance(pm, dict) else {}}, True
            except Exception as e:
                errors.append(f"rule {rid}: extension action '{kind}' failed: {e}")
        return None, False
    except Exception as e:
        errors.append(f"rule {rid}: action error: {e}")
        return None, False


def apply_staged_actions(*, staged: List[Tuple[int, str, dict]], v2: Dict[str, Any], prev_state: Dict[str, Any], proj_mut: Dict[str, Any]):
    set_num: Dict[str, List[Tuple[int, float]]] = {}
    pulsed_vars: set[str] = set()
    set_num_policy: Dict[str, str] = {}
    add_num: Dict[str, float] = {}
    set_toggle: Dict[str, List[Tuple[int, bool]]] = {}
    set_toggle_policy: Dict[str, str] = {}
    flip_toggle_count: Dict[str, int] = {}
    set_layer: Dict[Tuple[int, str], List[Tuple[int, Any]]] = {}
    set_layer_policy: Dict[Tuple[int, str], str] = {}

    for (sseq, rid, a) in staged:
        ak = str((a or {}).get("kind", "") or "")
        if ak == "__extension__":
            pm = (a or {}).get("project_mutations")
            if isinstance(pm, dict) and pm:
                proj_mut.update(pm)
            continue
        if ak in ("set_var", "add_var", "pulse_var"):
            vkind = str((a or {}).get("var_kind", "number") or "number")
            vname = str((a or {}).get("var", "") or "")
            if not vname:
                continue
            if vkind == "toggle":
                bv = bool((a or {}).get("value", False))
                if ak == "set_var":
                    set_toggle.setdefault(vname, []).append((sseq, bv))
                    set_toggle_policy.setdefault(vname, str((a or {}).get("conflict", "last") or "last"))
                elif ak == "pulse_var":
                    set_toggle.setdefault(vname, []).append((sseq, bv))
                    set_toggle_policy.setdefault(vname, "last")
                    try:
                        if isinstance(prev_state, dict):
                            prev_state.setdefault("_pulse_reset_toggles", [])
                            prev_state["_pulse_reset_toggles"].append(vname)
                    except Exception as e:
                        _diag_exc(e, stage="pulse_toggle_register", rule_id=rid, details={"var": vname})
                else:
                    set_toggle.setdefault(vname, []).append((sseq, bv))
                    set_toggle_policy.setdefault(vname, "or")
            else:
                fv = _to_float((a or {}).get("value", 0.0), 0.0)
                if ak == "set_var":
                    set_num.setdefault(vname, []).append((sseq, fv))
                    set_num_policy.setdefault(vname, str((a or {}).get("conflict", "last") or "last"))
                elif ak == "pulse_var":
                    set_num.setdefault(vname, []).append((sseq, fv))
                    set_num_policy.setdefault(vname, "last")
                    pulsed_vars.add(vname)
                else:
                    add_num[vname] = add_num.get(vname, 0.0) + fv
        elif ak == "flip_toggle":
            vname = str((a or {}).get("var", "") or "")
            if not vname:
                continue
            flip_toggle_count[vname] = flip_toggle_count.get(vname, 0) + 1
        elif ak == "set_layer_param":
            try:
                li = int((a or {}).get("layer", 0) or 0)
            except Exception as e:
                _diag_exc(e, stage="apply_parse_layer_index", rule_id=str(rid), details={"value": repr((a or {}).get("layer"))})
                li = 0
            param = str((a or {}).get("param", "") or "")
            if not param:
                continue
            key = (li, param)
            set_layer.setdefault(key, []).append((sseq, (a or {}).get("value")))
            set_layer_policy.setdefault(key, str((a or {}).get("conflict", "last") or "last"))

    for vname, vals in set_num.items():
        vals.sort(key=lambda t: t[0])
        v2["number"][vname] = _resolve_num(vals, set_num_policy.get(vname, "last"))
    for vname, addv in add_num.items():
        cur = _to_float(v2["number"].get(vname, 0.0), 0.0)
        v2["number"][vname] = cur + float(addv)
    for vname, vals in set_toggle.items():
        vals.sort(key=lambda t: t[0])
        v2["toggle"][vname] = _resolve_bool(vals, set_toggle_policy.get(vname, "last"))
    for vname, cnt in flip_toggle_count.items():
        if cnt % 2 == 0:
            continue
        cur = bool(v2["toggle"].get(vname, False))
        v2["toggle"][vname] = (not cur)
    if set_layer:
        out = []
        for key, vals in set_layer.items():
            vals.sort(key=lambda t: t[0])
            pol = (set_layer_policy.get(key, "last") or "last").lower().strip()
            v = vals[0][1] if pol == "first" else vals[-1][1]
            out.append((key[0], key[1], v))
        proj_mut.setdefault("layer_param", []).extend(out)
    try:
        if isinstance(prev_state, dict) and pulsed_vars:
            prev_state["_pulse_reset_vars"] = list(pulsed_vars)
    except Exception as e:
        _diag_exc(e, stage="pulse_var_register")
