from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from app.triage_report_build import *
from app.project_apply import apply_project_root
from app.triage_report_debt import (
    _domain_closure_candidates,
    _domain_closure_readiness,
    _domain_exit_criteria,
)
from app.triage_report_build import _domain_for_address


def _previous_closed_domains(project: Dict[str, Any]) -> List[str]:
    if not isinstance(project, dict):
        return []
    ui = project.get("ui") or {}
    if not isinstance(ui, dict):
        return []
    items = ui.get("triage_closed_domains") or []
    if not isinstance(items, list):
        return []
    return [str(x) for x in items if x]

def _store_closed_domains(project: Dict[str, Any], domains: List[str]) -> None:
    if not isinstance(project, dict):
        return
    ui0 = project.get("ui")
    ui = dict(ui0) if isinstance(ui0, dict) else {}
    ui["triage_closed_domains"] = list(domains)
    p2, _validation, _changes = apply_project_root(project, "ui", ui)
    project.clear()
    project.update(p2)

def _closure_ledger(previous_domains: List[str], current_domains: List[str], rows, fix_rows, proof_rows, delta) -> List[Tuple[str, str, str]]:
    prev = set(previous_domains or [])
    curr = set(current_domains or [])
    out: List[Tuple[str, str, str]] = []
    for domain in sorted(curr):
        if domain not in prev:
            out.append((domain, "newly_closed", "ready candidate now has certificate-quality evidence and no sampled regression"))
        else:
            out.append((domain, "still_closed", "remains closure-candidate clean against sampled debt and delta checks"))
    reopened = sorted(prev - curr)
    for domain in reopened:
        domain_fix = sum(1 for row in fix_rows if _domain_for_address(row[0]) == domain)
        domain_proof = sum(1 for row in proof_rows if _domain_for_address(row[0]) == domain)
        regress = [addr for addr in (delta.get("regressions") or []) if _domain_for_address(addr) == domain]
        reason_bits = []
        if domain_fix:
            reason_bits.append(f"fix={domain_fix}")
        if domain_proof:
            reason_bits.append(f"proof={domain_proof}")
        if regress:
            reason_bits.append(f"regressions={len(regress)}")
        why = ", ".join(reason_bits) if reason_bits else "closure candidate conditions no longer hold"
        out.append((domain, "reopened", why))
    return out

def _closure_decisions(rows, fix_rows, proof_rows, delta, address_rows, ledger_rows):
    exit_map = {d: txt for d, txt in _domain_exit_criteria(rows, fix_rows, proof_rows)}
    """Operational close/hold/reopen decisions derived from the closure system.

    This is the first place triage stops merely reporting candidates and starts
    recommending a concrete closure action per domain.
    """
    cert_map = {domain: (proof, regress, close_if) for domain, proof, regress, close_if in _domain_closure_certificates(rows, fix_rows, proof_rows, delta, address_rows)}
    ledger_map = {domain: (state, why) for domain, state, why in ledger_rows}
    out = []
    seen = set()
    for domain, _status, _detail in rows:
        seen.add(domain)
        led_state, led_why = ledger_map.get(domain, ('open', 'not a current closure candidate'))
        cert = cert_map.get(domain)
        if led_state in ('newly_closed', 'still_closed') and cert:
            action = 'CLOSE_NOW' if led_state == 'newly_closed' else 'KEEP_CLOSED'
            note = cert[2] if len(cert) > 2 else led_why
            out.append((domain, action, led_why, note))
            continue
        if led_state == 'reopened':
            out.append((domain, 'REOPEN', led_why, 'clear the reopened debt/regression before closing again'))
            continue
        readiness = {d: (r, reason) for d, r, reason in _domain_closure_readiness(rows, fix_rows, proof_rows)}.get(domain, ('PROVING', 'triage incomplete'))
        action = 'HOLD_BLOCKED' if readiness[0] == 'BLOCKED' else 'HOLD_PROVING'
        out.append((domain, action, readiness[1], exit_map.get(domain, readiness[1])))
    return out

def _domain_closure_certificates(rows, fix_rows, proof_rows, delta, address_rows):
    certificates = []
    exit_map = {d: txt for d, txt in _domain_exit_criteria(rows, fix_rows, proof_rows)}
    candidate_domains = [domain for domain, _note in _domain_closure_candidates(rows, fix_rows, proof_rows, delta)]
    for domain in candidate_domains:
        domain_rows = [row for row in address_rows if _domain_for_address(row[0]) == domain]
        direct = sum(1 for row in domain_rows if row[12] == "direct")
        partial = sum(1 for row in domain_rows if row[12] == "partial")
        inferred = sum(1 for row in domain_rows if row[12] == "inferred")
        low = sum(1 for row in domain_rows if row[12] == "low")
        open_n = sum(1 for row in domain_rows if row[1] == "OPEN")
        split_n = sum(1 for row in domain_rows if row[1] == "SPLIT")
        closed_n = sum(1 for row in domain_rows if row[1] == "CLOSED")
        regressions = [addr for addr in (delta.get("regressions") or []) if _domain_for_address(addr) == domain]
        certificates.append((
            domain,
            f"OPEN={open_n} SPLIT={split_n} CLOSED={closed_n}; confidence direct={direct} partial={partial} inferred={inferred} low={low}",
            "no current regressions" if not regressions else f"regressions present: {', '.join(regressions[:4])}",
            exit_map.get(domain, 'not ready: exit criteria unavailable'),
        ))
    return certificates
