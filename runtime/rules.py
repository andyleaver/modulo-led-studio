"""Rules engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .rules_apply import apply_staged_actions, stage_rule_action
from .rules_support import _diag_exc
from .rules_triggers import evaluate_conditions, evaluate_trigger, rule_sort_key


def ensure_rules(project: dict) -> Tuple[dict, bool]:
    """Ensure the canonical rules root exists without re-entering project canonicalization.

    This helper is used by both runtime and project canonicalization, so it must
    remain cycle-free. Canonical load/finalize code can perform any broader
    validation separately; this function only guarantees the authored root key is
    present and list-typed.
    """
    p = project if isinstance(project, dict) else {}
    r0 = p.get("rules")
    if isinstance(r0, list):
        return p, False
    p2 = dict(p)
    p2["rules"] = []
    return p2, True


@dataclass
class RuleEvalResult:
    variables_state: Dict[str, Any]
    project_mutations: Dict[str, Any]
    errors: List[str]
    fired_rule_ids: List[str]


def evaluate_rules(
    *,
    project: dict,
    signals: Dict[str, Any],
    variables_state: Dict[str, Any],
    prev_state: Dict[str, Any],
    allow_layer_param_mutation: bool = True,
) -> RuleEvalResult:
    p = project if isinstance(project, dict) else {}
    rules = p.get("rules")
    rules_list = list(rules or []) if isinstance(rules, list) else []

    vstate = variables_state if isinstance(variables_state, dict) else {}
    v2 = {
        "number": dict(vstate.get("number") or {}) if isinstance(vstate.get("number"), dict) else {},
        "toggle": dict(vstate.get("toggle") or {}) if isinstance(vstate.get("toggle"), dict) else {},
    }

    try:
        if isinstance(prev_state, dict):
            prs = prev_state.get("_pulse_reset_vars")
            if isinstance(prs, list):
                for vn in prs:
                    if isinstance(vn, str) and vn:
                        v2["number"][vn] = 0.0
            prev_state["_pulse_reset_vars"] = []
            pt = prev_state.get("_pulse_reset_toggles")
            if isinstance(pt, list):
                for vn in pt:
                    if isinstance(vn, str) and vn:
                        v2["toggle"][vn] = False
            prev_state["_pulse_reset_toggles"] = []
    except Exception as e:
        _diag_exc(e, stage="pulse_reset")

    rules_list.sort(key=rule_sort_key)

    errors: List[str] = []
    fired: List[str] = []
    proj_mut: Dict[str, Any] = {}
    staged: List[Tuple[int, str, dict]] = []
    seq = 0

    for r in rules_list:
        rr = r if isinstance(r, dict) else {}
        rid = str(rr.get("id", "") or "")
        if not rid or not bool(rr.get("enabled", True)):
            if not rid:
                continue
        if not rid:
            continue
        from .rules_support import _to_bool
        if not _to_bool(rr.get("enabled", True)):
            continue
        if not evaluate_trigger(rr, signals=signals, prev_state=prev_state, errors=errors):
            continue
        if not evaluate_conditions(rr, signals=signals, prev_state=prev_state, errors=errors):
            continue
        action, did_fire = stage_rule_action(
            rr,
            signals=signals,
            v2=v2,
            prev_state=prev_state,
            errors=errors,
            allow_layer_param_mutation=allow_layer_param_mutation,
        )
        if action is None:
            continue
        staged.append((seq, rid, action))
        seq += 1
        if did_fire:
            fired.append(rid)

    apply_staged_actions(staged=staged, v2=v2, prev_state=prev_state, proj_mut=proj_mut)
    return RuleEvalResult(variables_state=v2, project_mutations=proj_mut, errors=errors, fired_rule_ids=fired)
