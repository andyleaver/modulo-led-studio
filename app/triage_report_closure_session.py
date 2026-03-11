from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from app.triage_report_build import *
from app.triage_report_debt import _domain_exit_criteria
from app.triage_report_build import _domain_for_address
from app.triage_report_metrics import _probe_outcome_hint


def _closure_session_plan(rows, fix_rows, proof_rows, decisions):
    """Single-session execution slice for the current triage run.

    Turns closure decisions/worksets into one concrete batch:
    the domain to work now, the probe to run first, and the top sampled
    addresses to clear/prove before moving on.
    """
    workset = _closure_workset(rows, fix_rows, proof_rows, decisions)
    if not workset:
        return None
    rank = {'REOPEN': 0, 'ACTIVE_FIX': 1, 'HOLD_BLOCKED': 2, 'ACTIVE_PROOF': 3, 'HOLD_PROVING': 4}
    domain, action, why, gate, items = sorted(
        workset,
        key=lambda entry: (rank.get(str(entry[1]), 9), -len(entry[4]), str(entry[0]))
    )[0]
    probe = 'Run Triage'
    if items:
        probe = str(items[0][14] or probe)
    return {
        'domain': domain,
        'action': action,
        'why': why,
        'gate': gate,
        'probe': probe,
        'addresses': items[:5],
    }

def _closure_workset(rows, fix_rows, proof_rows, decisions):
    """Top actionable addresses per domain decision.

    Gives triage an execution batch instead of only domain-level decisions.
    """
    by_domain = OrderedDict()
    for row in list(fix_rows) + list(proof_rows):
        by_domain.setdefault(_domain_for_address(row[0]), []).append(row)
    out = []
    for domain, action, why, gate in decisions:
        if action in ('KEEP_CLOSED', 'CLOSE_NOW'):
            continue
        items = by_domain.get(domain, [])
        ranked = sorted(items, key=lambda row: ({'CLOSED': 0, 'SPLIT': 1, 'OPEN': 2}.get(str(row[1]), 3), {'low': 0, 'inferred': 1, 'partial': 2, 'direct': 3}.get(str(row[12]), 4), str(row[0])))
        out.append((domain, action, why, gate, ranked[:3]))
    return out

def _execution_pack_from_session(session: Optional[Dict[str, Any]], rows=None, fix_rows=None, proof_rows=None) -> Optional[Dict[str, Any]]:
    """Turn the current closure session into a reusable execution pack.

    The pack is intentionally small and explicit so diagnostics can re-use it
    as a single source of truth for the current triage slice.
    """
    if not session:
        return None
    items = list(session.get('addresses') or [])
    probe = str(session.get('probe') or 'Run Triage')
    domain = str(session.get('domain') or 'unknown')
    action = str(session.get('action') or 'HOLD_PROVING')
    exit_map = {d: txt for d, txt in _domain_exit_criteria(rows or [], fix_rows or [], proof_rows or [])} if (rows is not None and fix_rows is not None and proof_rows is not None) else {}
    gate = str(session.get('gate') or exit_map.get(domain) or 'not ready: exit criteria unavailable')
    reasons = []
    for row in items:
        try:
            reason = str(row[13] or '').strip()
        except Exception:
            reason = ''
        if reason and reason not in reasons:
            reasons.append(reason)
    outcome_target = 'raise confidence and clear sampled debt for the selected addresses'
    if items:
        top = items[0]
        outcome_target = _probe_outcome_hint(top)
    return {
        'domain': domain,
        'decision': action,
        'probe': probe,
        'addresses': [str(row[0]) for row in items],
        'close_with': gate,
        'reason_codes': reasons,
        'session_outcome_target': outcome_target,
    }

def _execution_pack_receipt(execution_pack: Optional[Dict[str, Any]], probe_results: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Summarise whether ingested probe results actually touched the active execution pack.

    This closes the loop another step: triage can now tell whether the current
    packet of work has received evidence, only partial evidence, or none.
    """
    if not execution_pack:
        return None
    results = probe_results if isinstance(probe_results, dict) else {}
    addresses = [str(a) for a in (execution_pack.get('addresses') or []) if a]
    touched = []
    positive = []
    negative = []
    for addr in addresses:
        payload = results.get(addr) or {}
        if not isinstance(payload, dict) or not payload:
            continue
        result = str(payload.get('result') or '').strip().lower()
        probe_name = str(payload.get('probe') or execution_pack.get('probe') or 'probe').strip()
        touched.append((addr, result or 'unknown', probe_name))
        if result in ('open', 'pass', 'proved'):
            positive.append(addr)
        elif result in ('split', 'mismatch', 'closed', 'fail', 'missing'):
            negative.append(addr)
    total = len(addresses)
    touched_n = len(touched)
    if total <= 0:
        state = 'NO_TARGETS'
        summary = 'execution pack has no sampled addresses'
    elif touched_n == 0:
        state = 'AWAITING_PROBES'
        summary = 'no stored probe outcomes yet for the current execution pack'
    elif touched_n < total and negative:
        state = 'PARTIAL_WITH_FAILURE'
        summary = f'partial coverage with blockers on {len(negative)} of {touched_n} touched addresses'
    elif touched_n < total:
        state = 'PARTIAL'
        summary = f'probe outcomes applied to {touched_n}/{total} execution-pack addresses'
    elif negative:
        state = 'BLOCKED_BY_RESULT'
        summary = f'probe outcomes touched all sampled addresses but {len(negative)} reported split/closed results'
    else:
        state = 'READY_TO_REEVALUATE'
        summary = 'probe outcomes touched all sampled addresses without blocker results; rerun triage to reassess closure'
    return {
        'state': state,
        'summary': summary,
        'touched': touched,
        'positive': positive,
        'negative': negative,
        'total': total,
    }

def _reevaluation_gate(execution_pack: Optional[Dict[str, Any]], execution_receipt: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Turn receipt state into the next operational triage action.

    This is the step after receipt: decide whether to rerun triage, gather
    more probe results, or investigate failures before attempting closure.
    """
    if not execution_pack:
        return None
    if not execution_receipt:
        return {
            "state": "NO_ACTIVE_SESSION",
            "next": "run_triage",
            "summary": "no active execution pack; rerun triage to select a new closure session",
        }
    state = str(execution_receipt.get("state") or "UNKNOWN")
    gate = str(execution_pack.get("close_with") or "satisfy current close gate")
    if state == 'READY_TO_REEVALUATE':
        return {
            "state": state,
            "next": "rerun_triage_now",
            "summary": f"execution pack received enough positive probe evidence; rerun triage and check close gate: {gate}",
        }
    if state == 'AWAITING_PROBES':
        return {
            "state": state,
            "next": "run_session_probe",
            "summary": "no probe outcomes have touched the active execution pack yet; run the selected probe first",
        }
    if state == 'PARTIAL':
        return {
            "state": state,
            "next": "complete_probe_coverage",
            "summary": "some execution-pack addresses have evidence, but more addresses still need probe coverage before reevaluating",
        }
    if state in ('PARTIAL_WITH_FAILURE', 'BLOCKED_BY_RESULT'):
        return {
            "state": state,
            "next": "investigate_failures",
            "summary": "probe results introduced split/closed evidence; inspect blocker reasons before rerunning triage",
        }
    return {
        "state": state,
        "next": "review_execution_receipt",
        "summary": "execution receipt is in an unknown state; review current probe outcomes and rerun triage if appropriate",
    }

def _reevaluation_transition(execution_pack: Optional[Dict[str, Any]], execution_receipt: Optional[Dict[str, Any]], reevaluation_gate: Optional[Dict[str, Any]], workset: List[Tuple[str, str, str, str, List[Tuple[str, ...]]]]) -> Optional[Dict[str, Any]]:
    """Advance triage from gate/receipt into the next explicit execution state.

     turns the reevaluation gate into a concrete transition object so the
    current closure session can roll forward instead of remaining advisory.
    """
    if not execution_pack or not reevaluation_gate:
        return None
    gate_next = str(reevaluation_gate.get('next') or 'review_execution_receipt')
    receipt_state = str((execution_receipt or {}).get('state') or 'UNKNOWN')
    transition = {
        'action': gate_next,
        'from_session': str(execution_pack.get('domain') or 'unknown'),
        'next_domain': str(execution_pack.get('domain') or 'unknown'),
        'next_probe': str(execution_pack.get('probe') or 'Run Triage'),
        'next_addresses': list(execution_pack.get('addresses') or []),
        'transition_reason': str(reevaluation_gate.get('summary') or ''),
    }
    if gate_next == 'rerun_triage_now':
        # Promote to the next actionable workset item if one exists; otherwise
        # stay on the current domain and mark it ready for closure review.
        if workset:
            domain, _action, _why, _gate, items = workset[0]
            transition['next_domain'] = domain
            transition['next_probe'] = str(items[0][14] if items else execution_pack.get('probe') or 'Run Triage')
            transition['next_addresses'] = [str(r[0]) for r in items[:3]] if items else []
        transition['action'] = 'advance_closure_state'
        transition['transition_reason'] = f"receipt={receipt_state}; rerun triage and rebuild closure decisions from new direct evidence"
    elif gate_next == 'investigate_failures':
        transition['action'] = 'route_failure_branch'
        touched = list((execution_receipt or {}).get('touched') or [])
        failing = [addr for addr, result, _probe in touched if str(result) in ('split', 'mismatch', 'closed', 'fail', 'missing')]
        if failing:
            transition['next_addresses'] = failing[:5]
        transition['transition_reason'] = f"receipt={receipt_state}; blocker results landed in the active execution pack"
    elif gate_next == 'complete_probe_coverage':
        transition['action'] = 'finish_current_session_coverage'
        transition['transition_reason'] = f"receipt={receipt_state}; gather missing probe outcomes before reevaluating closure"
    elif gate_next == 'run_session_probe':
        transition['action'] = 'execute_current_probe'
        transition['transition_reason'] = 'no probe outcomes have touched the active execution pack yet'
    return transition
