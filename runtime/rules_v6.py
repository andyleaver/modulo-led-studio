"""Rules (Phase 6.3)

Deterministic Rules/Triggers operating on the Phase 6 signal bus.

This is an MVP intended to be:
  - safe (never crash the app)
  - deterministic (stable ordering, stable edge tracking)
  - inspectable (simple schema, explicit errors)

Schema (project["rules_v6"]):

Each rule is a dict with:
  id: str (required)
  enabled: bool
  name: str
  trigger: "tick" | "threshold" | "rising"

  when:
    signal: str
    op: ">" | ">=" | "<" | "<=" | "=="  (threshold only)
    value: float                             (threshold only)
    hyst: float                              (threshold only)

  cond_mode: "all" | "any" (optional; default "all")

  conditions: [
    {"signal": str, "op": ">"|">="|"<"|"<="|"==", "value": float},
    ...
  ]

  action:
    kind: "set_var" | "add_var" | "flip_toggle" | "set_layer_param"   (layer action is preview-only in MVP)
    var_kind: "number" | "toggle"                       (for var actions)
    var: str                                                (for var actions)
    layer: int                                              (for layer action)
    param: str                                              (for layer action)
    expr:
      src: "const" | "signal"
      const: float
      signal: str
      scale: float
      bias: float
      as_bool: bool (optional)  # if True, expr becomes (value>0.5)

Rules are executed in stable order by (name,id). Edge/threshold state is
maintained in a separate runtime dict (prev_state) keyed by rule id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


def _clampf(x: float, lo: float, hi: float) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def _to_bool(x: Any) -> bool:
    try:
        if isinstance(x, bool):
            return x
        if isinstance(x, (int, float)):
            return float(x) != 0.0
        if isinstance(x, str):
            return x.strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        pass
    return False


def _to_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def ensure_rules_v6(project: dict) -> Tuple[dict, bool]:
    p = project if isinstance(project, dict) else {}
    r0 = p.get("rules_v6")
    if isinstance(r0, list):
        return p, False
    p2 = dict(p)
    p2["rules_v6"] = []
    return p2, True


@dataclass
class RuleEvalResult:
    variables_state: Dict[str, Any]
    project_mutations: Dict[str, Any]
    errors: List[str]
    fired_rule_ids: List[str]


def _eval_expr(expr: dict, signals: Dict[str, Any]) -> Any:
    e = expr if isinstance(expr, dict) else {}
    src = str(e.get("src", "const") or "const")
    scale = _to_float(e.get("scale", 1.0), 1.0)
    bias = _to_float(e.get("bias", 0.0), 0.0)
    if src == "signal":
        name = str(e.get("signal", "") or "")
        v = signals.get(name, 0.0)
        out = _to_float(v, 0.0) * scale + bias
    else:
        out = _to_float(e.get("const", 0.0), 0.0) * scale + bias

    if _to_bool(e.get("as_bool", False)):
        return bool(out > 0.5)
    return out


def _cmp(a: float, op: str, b: float) -> bool:
    if op == ">":
        return a > b
    if op == ">=":
        return a >= b
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    if op == "==":
        return a == b
    return a > b


def _threshold_eval(cur: float, op: str, thr: float, hyst: float, prev: Optional[bool]) -> bool:
    """Threshold with hysteresis.

    If prev is True, we require falling below (thr - hyst) to turn False.
    If prev is False/None, we require exceeding (thr + hyst) to turn True.
    """
    h = abs(_to_float(hyst, 0.0))
    if prev:
        # Stay true unless we cross the off threshold.
        off_thr = thr - h
        return _cmp(cur, op, off_thr) if op in ("<", "<=") else (cur >= off_thr)
    else:
        on_thr = thr + h
        return _cmp(cur, op, on_thr) if op in ("<", "<=") else (cur >= on_thr)


def evaluate_rules_v6(
    *,
    project: dict,
    signals: Dict[str, Any],
    variables_state: Dict[str, Any],
    prev_state: Dict[str, Any],
    allow_layer_param_mutation: bool = True,
) -> RuleEvalResult:
    """Evaluate Phase 6 rules.

    Returns:
      - updated variables_state (dict)
      - project_mutations (only for layer param actions; empty if none)
      - errors list
      - fired_rule_ids list
    """
    p = project if isinstance(project, dict) else {}
    rules = p.get("rules_v6")
    rules_list = list(rules or []) if isinstance(rules, list) else []

    # Copy variables_state so evaluation is pure-ish.
    vstate = variables_state if isinstance(variables_state, dict) else {}
    v2 = {
        "number": dict(vstate.get("number") or {}) if isinstance(vstate.get("number"), dict) else {},
        "toggle": dict(vstate.get("toggle") or {}) if isinstance(vstate.get("toggle"), dict) else {},
    }

    # Stable ordering
    def _rk(r: dict) -> Tuple[str, str]:
        try:
            name = str((r or {}).get("name", "") or "")
        except Exception:
            name = ""
        try:
            rid = str((r or {}).get("id", "") or "")
        except Exception:
            rid = ""
        return (name, rid)

    rules_list.sort(key=_rk)

    errors: List[str] = []
    fired: List[str] = []
    proj_mut: Dict[str, Any] = {}
    staged: List[Tuple[int, str, dict]] = []  # (seq, rule_id, action_dict)
    seq = 0

    for r in rules_list:
        rr = r if isinstance(r, dict) else {}
        rid = str(rr.get("id", "") or "")
        if not rid:
            continue
        if not _to_bool(rr.get("enabled", True)):
            continue

        trig = str(rr.get("trigger", "tick") or "tick")

        should_fire = False
        try:
            if trig == "tick":
                should_fire = True
            elif trig == "rising":
                when = rr.get("when") if isinstance(rr.get("when"), dict) else {}
                sname = str((when or {}).get("signal", "") or "")
                cur = _to_bool(signals.get(sname, False))
                prev = _to_bool(prev_state.get(f"rise:{rid}", False))
                should_fire = (not prev) and cur
                prev_state[f"rise:{rid}"] = bool(cur)
            elif trig == "threshold":
                when = rr.get("when") if isinstance(rr.get("when"), dict) else {}
                sname = str((when or {}).get("signal", "") or "")
                op = str((when or {}).get("op", ">") or ">")
                thr = _to_float((when or {}).get("value", 0.0), 0.0)
                hyst = _to_float((when or {}).get("hyst", 0.0), 0.0)
                curf = _to_float(signals.get(sname, 0.0), 0.0)
                prev_on = prev_state.get(f"thr:{rid}")
                prevb = bool(prev_on) if isinstance(prev_on, bool) else False
                on = _threshold_eval(curf, op, thr, hyst, prevb)
                # Fire on edge (off->on)
                should_fire = (not prevb) and on
                prev_state[f"thr:{rid}"] = bool(on)
            else:
                # Unknown trigger => ignore
                continue
        except Exception as e:
            errors.append(f"rule {rid}: trigger error: {e}")
            continue

        if not should_fire:
            continue

        # Optional AND conditions gate.
        try:
            conds = rr.get("conditions")
            cond_list = list(conds or []) if isinstance(conds, list) else []
        except Exception:
            cond_list = []

        cond_ok = True
        cond_mode = str(rr.get("cond_mode", "all") or "all")
        if cond_mode not in ("all", "any"):
            cond_mode = "all"
        try:
            if not cond_list:
                cond_ok = True
            elif cond_mode == "any":
                any_true = False
                for c0 in cond_list:
                    c = c0 if isinstance(c0, dict) else {}
                    sname = str((c or {}).get("signal", "") or "")
                    if not sname:
                        continue
                    op = str((c or {}).get("op", ">") or ">")
                    if op not in (">", ">=", "<", "<=", "=="):
                        errors.append(f"rule {rid}: invalid condition op '{op}'")
                        cond_ok = False
                        break
                    if sname not in signals:
                        errors.append(f"rule {rid}: condition signal '{sname}' missing")
                        cond_ok = False
                        break
                    curf = _to_float(signals.get(sname, 0.0), 0.0)
                    thr = _to_float((c or {}).get("value", 0.0), 0.0)
                    if _cmp(curf, op, thr):
                        any_true = True
                cond_ok = bool(cond_ok and any_true)
            else:
                for c0 in cond_list:
                    c = c0 if isinstance(c0, dict) else {}
                    sname = str((c or {}).get("signal", "") or "")
                    if not sname:
                        continue
                    op = str((c or {}).get("op", ">") or ">")
                    if op not in (">", ">=", "<", "<=", "=="):
                        errors.append(f"rule {rid}: invalid condition op '{op}'")
                        cond_ok = False
                        break
                    if sname not in signals:
                        errors.append(f"rule {rid}: condition signal '{sname}' missing")
                        cond_ok = False
                        break
                    curf = _to_float(signals.get(sname, 0.0), 0.0)
                    thr = _to_float((c or {}).get("value", 0.0), 0.0)
                    if not _cmp(curf, op, thr):
                        cond_ok = False
                        break
        except Exception as e:
            errors.append(f"rule {rid}: condition error: {e}")
            cond_ok = False

        try:
            prev_state[f"cond:{rid}"] = bool(cond_ok)
        except Exception:
            pass

        if not cond_ok:
            continue

        act = rr.get("action") if isinstance(rr.get("action"), dict) else {}
        kind = str((act or {}).get("kind", "") or "")
        try:
            if kind in ("set_var", "add_var"):
                vkind = str((act or {}).get("var_kind", "number") or "number")
                vname = str((act or {}).get("var", "") or "")
                if not vname:
                    errors.append(f"rule {rid}: missing var name")
                    continue
                if vkind not in ("number", "toggle"):
                    errors.append(f"rule {rid}: invalid var_kind '{vkind}'")
                    continue

                expr = (act or {}).get("expr") if isinstance((act or {}).get("expr"), dict) else {}
                val = _eval_expr(expr, signals)
                conflict = str((act or {}).get("conflict", "last") or "last")

                staged.append((seq, rid, {
                    "kind": kind,
                    "var_kind": vkind,
                    "var": vname,
                    "value": val,
                    "conflict": conflict,
                }))
                seq += 1
                fired.append(rid)

            elif kind == "flip_toggle":
                vname = str((act or {}).get("var", "") or "")
                if not vname:
                    errors.append(f"rule {rid}: missing var name")
                    continue
                staged.append((seq, rid, {
                    "kind": "flip_toggle",
                    "var_kind": "toggle",
                    "var": vname,
                }))
                seq += 1
                fired.append(rid)

            elif kind == "set_layer_param":
                if not allow_layer_param_mutation:
                    errors.append(f"rule {rid}: layer param actions disabled")
                    continue
                try:
                    li = int((act or {}).get("layer", 0) or 0)
                except Exception:
                    li = 0
                param = str((act or {}).get("param", "") or "")
                if not param:
                    errors.append(f"rule {rid}: missing layer param")
                    continue
                expr = (act or {}).get("expr") if isinstance((act or {}).get("expr"), dict) else {}
                val = _eval_expr(expr, signals)
                conflict = str((act or {}).get("conflict", "last") or "last")
                staged.append((seq, rid, {
                    "kind": "set_layer_param",
                    "layer": li,
                    "param": param,
                    "value": val,
                    "conflict": conflict,
                }))
                seq += 1
                fired.append(rid)
            else:
                continue
        except Exception as e:
            errors.append(f"rule {rid}: action error: {e}")
            continue

    # -------------------------
    # Apply staged actions (deterministic conflict policy)
    # -------------------------

    def _resolve_num(values: List[Tuple[int, float]], policy: str) -> float:
        if not values:
            return 0.0
        p = (policy or "last").lower().strip()
        if p == "first":
            return values[0][1]
        if p == "max":
            return max(v for _, v in values)
        if p == "min":
            return min(v for _, v in values)
        return values[-1][1]

    def _resolve_bool(values: List[Tuple[int, bool]], policy: str) -> bool:
        if not values:
            return False
        p = (policy or "last").lower().strip()
        if p == "first":
            return bool(values[0][1])
        if p == "or":
            out = False
            for _, v in values:
                out = out or bool(v)
            return out
        if p == "and":
            out = True
            for _, v in values:
                out = out and bool(v)
            return out
        if p == "xor":
            out = False
            for _, v in values:
                out = (out != bool(v))
            return out
        return bool(values[-1][1])

    set_num: Dict[str, List[Tuple[int, float]]] = {}
    set_num_policy: Dict[str, str] = {}
    add_num: Dict[str, float] = {}

    set_toggle: Dict[str, List[Tuple[int, bool]]] = {}
    set_toggle_policy: Dict[str, str] = {}
    flip_toggle_count: Dict[str, int] = {}

    set_layer: Dict[Tuple[int, str], List[Tuple[int, Any]]] = {}
    set_layer_policy: Dict[Tuple[int, str], str] = {}

    for (sseq, _rid, a) in staged:
        ak = str((a or {}).get("kind", "") or "")
        if ak in ("set_var", "add_var"):
            vkind = str((a or {}).get("var_kind", "number") or "number")
            vname = str((a or {}).get("var", "") or "")
            if not vname:
                continue
            if vkind == "toggle":
                bv = bool((a or {}).get("value", False))
                if ak == "set_var":
                    set_toggle.setdefault(vname, []).append((sseq, bv))
                    set_toggle_policy.setdefault(vname, str((a or {}).get("conflict", "last") or "last"))
                else:
                    set_toggle.setdefault(vname, []).append((sseq, bv))
                    set_toggle_policy.setdefault(vname, "or")
            else:
                fv = _to_float((a or {}).get("value", 0.0), 0.0)
                if ak == "set_var":
                    set_num.setdefault(vname, []).append((sseq, fv))
                    set_num_policy.setdefault(vname, str((a or {}).get("conflict", "last") or "last"))
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
            except Exception:
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

    return RuleEvalResult(variables_state=v2, project_mutations=proj_mut, errors=errors, fired_rule_ids=fired)
