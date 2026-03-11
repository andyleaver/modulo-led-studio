from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .rules_support import _cmp, _diag_exc, _threshold_eval, _to_bool, _to_float


def rule_sort_key(rule: dict) -> Tuple[str, str]:
    try:
        name = str((rule or {}).get("name", "") or "")
    except Exception as e:
        _diag_exc(e, stage="sort_key:name")
        name = ""
    try:
        rid = str((rule or {}).get("id", "") or "")
    except Exception as e:
        _diag_exc(e, stage="sort_key:id")
        rid = ""
    return (name, rid)


def evaluate_trigger(rule: dict, *, signals: Dict[str, Any], prev_state: Dict[str, Any], errors: List[str]) -> bool:
    rr = rule if isinstance(rule, dict) else {}
    rid = str(rr.get("id", "") or "")
    trig = str(rr.get("trigger", "tick") or "tick")
    try:
        if trig == "tick":
            return True
        if trig == "rising":
            when = rr.get("when") if isinstance(rr.get("when"), dict) else {}
            sname = str((when or {}).get("signal", "") or "")
            cur = _to_bool(signals.get(sname, False))
            prev = _to_bool(prev_state.get(f"rise:{rid}", False))
            prev_state[f"rise:{rid}"] = bool(cur)
            return (not prev) and cur
        if trig == "threshold":
            when = rr.get("when") if isinstance(rr.get("when"), dict) else {}
            sname = str((when or {}).get("signal", "") or "")
            op = str((when or {}).get("op", ">") or ">")
            thr = _to_float((when or {}).get("value", 0.0), 0.0)
            hyst = _to_float((when or {}).get("hyst", 0.0), 0.0)
            curf = _to_float(signals.get(sname, 0.0), 0.0)
            prev_on = prev_state.get(f"thr:{rid}")
            prevb = bool(prev_on) if isinstance(prev_on, bool) else False
            on = _threshold_eval(curf, op, thr, hyst, prevb)
            prev_state[f"thr:{rid}"] = bool(on)
            return (not prevb) and on
        return False
    except Exception as e:
        errors.append(f"rule {rid}: trigger error: {e}")
        return False


def evaluate_conditions(rule: dict, *, signals: Dict[str, Any], prev_state: Dict[str, Any], errors: List[str]) -> bool:
    rr = rule if isinstance(rule, dict) else {}
    rid = str(rr.get("id", "") or "")
    try:
        conds = rr.get("conditions")
        cond_list = list(conds or []) if isinstance(conds, list) else []
    except Exception:
        _diag_exc(Exception("read_conditions"), stage="read_conditions", rule_id=rid)
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
        _diag_exc(Exception("write_prev_state_cond"), stage="write_prev_state_cond", rule_id=rid)
    return cond_ok
