from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _diag_exc(e: Exception, *, stage: str, rule_id: str = "", details: Optional[Dict[str, Any]] = None) -> None:
    try:
        from runtime.diagnostics import GLOBAL_DIAGS

        d: Dict[str, Any] = {"file": "runtime/rules.py", "stage": stage}
        if rule_id:
            d["rule_id"] = rule_id
        if isinstance(details, dict) and details:
            d.update(details)
        GLOBAL_DIAGS.exception(
            e,
            domain="RULES",
            code="RULES_EXCEPTION",
            summary=f"rules exception ({stage})",
            details=d,
        )
    except Exception:
        return


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
    except Exception as e:
        _diag_exc(e, stage="to_bool")
    return False


def _to_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception as e:
        _diag_exc(e, stage="to_float", details={"value": repr(x)})
        return float(default)


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
        c = e.get("const", 0.0)
        if isinstance(c, str) and scale == 1.0 and bias == 0.0 and not _to_bool(e.get("as_bool", False)):
            out = c
        else:
            out = _to_float(c, 0.0) * scale + bias

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
    h = abs(_to_float(hyst, 0.0))
    if prev:
        off_thr = thr - h
        return _cmp(cur, op, off_thr) if op in ("<", "<=") else (cur >= off_thr)
    else:
        on_thr = thr + h
        return _cmp(cur, op, on_thr) if op in ("<", "<=") else (cur >= on_thr)


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
