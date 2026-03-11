from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.triage_report_build import *
from app.triage_report_build import _domain_for_address
from app.triage_report_metrics import _probe_outcome_hint

Status = str


def _domain_execution_state(rows: List[Tuple[str, Status, str]], fix_rows: List[Tuple[str, ...]], proof_rows: List[Tuple[str, ...]]) -> List[Tuple[str, str, str, str]]:
    readiness = {d: (r, reason) for d, r, reason in _domain_closure_readiness(rows, fix_rows, proof_rows)}
    queue = {d: (r, f, p, reason, probe) for d, r, f, p, reason, probe in _domain_closure_queue(rows, fix_rows, proof_rows)}
    out: List[Tuple[str, str, str, str]] = []
    for domain, status, detail in rows:
        ready_state, ready_reason = readiness.get(domain, ('PROVING', detail or 'still needs proof'))
        q = queue.get(domain)
        next_probe = q[4] if q else 'Run Triage'
        if ready_state == 'READY':
            state = 'CLOSED'
            why = 'domain exit criteria satisfied for sampled addresses'
        elif ready_state == 'BLOCKED':
            state = 'ACTIVE_FIX'
            why = ready_reason
        else:
            state = 'ACTIVE_PROOF'
            why = ready_reason
        out.append((domain, state, why, next_probe))
    return out


def _domain_closure_candidates(rows: List[Tuple[str, Status, str]], fix_rows: List[Tuple[str, ...]], proof_rows: List[Tuple[str, ...]], delta: Dict[str, Any]) -> List[Tuple[str, str]]:
    debt_map = {d: (f, p) for d, f, p in _domain_debt_totals(fix_rows, proof_rows)}
    readiness_map = {d: (r, reason) for d, r, reason in _domain_closure_readiness(rows, fix_rows, proof_rows)}
    regressions = set(delta.get('regressions') or [])
    out: List[Tuple[str, str]] = []
    for domain, _status, _detail in rows:
        ready_state, _ready_reason = readiness_map.get(domain, ('PROVING', 'still needs proof'))
        fix_n, proof_n = debt_map.get(domain, (0, 0))
        domain_regressed = any(_domain_for_address(addr) == domain for addr in regressions)
        if ready_state == 'READY' and fix_n == 0 and proof_n == 0 and not domain_regressed:
            out.append((domain, 'ready to close now; sampled debt cleared and no current regressions touch this domain'))
        elif ready_state == 'READY' and domain_regressed:
            out.append((domain, 'looks ready but delta shows a regression in this domain; verify before closing'))
    return out


def _domain_debt_totals(fix_rows: List[Tuple[str, ...]], proof_rows: List[Tuple[str, ...]]) -> List[Tuple[str, int, int]]:
    domains = []
    for row in fix_rows:
        domains.append(_domain_for_address(row[0]))
    for row in proof_rows:
        domains.append(_domain_for_address(row[0]))
    out: List[Tuple[str, int, int]] = []
    for domain in sorted(set(domains)):
        fix_n = sum(1 for row in fix_rows if _domain_for_address(row[0]) == domain)
        proof_n = sum(1 for row in proof_rows if _domain_for_address(row[0]) == domain)
        out.append((domain, fix_n, proof_n))
    return out


def _fix_debt_rows(rows: List[Tuple[str, ...]]) -> List[Tuple[str, ...]]:
    out = []
    for row in rows:
        status = str(row[1]).upper()
        blocker = str(row[10] or '').strip().lower()
        if status == 'SPLIT' or status == 'CLOSED':
            out.append(row + (_probe_outcome_hint(row),))
        elif blocker and blocker not in ('none',):
            out.append(row + (_probe_outcome_hint(row),))
    return out


def _proof_debt_rows(rows: List[Tuple[str, ...]]) -> List[Tuple[str, ...]]:
    out = []
    for row in rows:
        status = str(row[1]).upper()
        blocker = str(row[10] or '').strip()
        confidence = str(row[12] or '').strip().lower()
        if status == 'OPEN' and not blocker and confidence not in ('direct', 'authoritative'):
            out.append(row + (_probe_outcome_hint(row),))
    return out


def _grouped_probe_plan(*row_groups: List[Tuple[str, ...]]) -> List[Tuple[str, List[Tuple[str, ...]]]]:
    out: Dict[str, List[Tuple[str, ...]]] = {}
    for rows in row_groups:
        for row in rows or []:
            probe = str((row[-2] if len(row) >= 2 else '') or 'Run Triage')
            out.setdefault(probe, []).append(row)
    return sorted(out.items(), key=lambda kv: (-len(kv[1]), kv[0]))


def _grouped_reason_plan(*row_groups: List[Tuple[str, ...]]) -> List[Tuple[str, List[Tuple[str, ...]]]]:
    out: Dict[str, List[Tuple[str, ...]]] = {}
    for rows in row_groups:
        for row in rows or []:
            reason = str((row[-1] if len(row) >= 1 else '') or 'No detail')
            out.setdefault(reason, []).append(row)
    return sorted(out.items(), key=lambda kv: (-len(kv[1]), kv[0]))


def _domain_closure_readiness(rows: List[Tuple[str, Status, str]], fix_rows: List[Tuple[str, ...]], proof_rows: List[Tuple[str, ...]]) -> List[Tuple[str, str, str]]:
    debt_map = {d: (f, p) for d, f, p in _domain_debt_totals(fix_rows, proof_rows)}
    out: List[Tuple[str, str, str]] = []
    for domain, status, detail in rows:
        fix_n, proof_n = debt_map.get(domain, (0, 0))
        if fix_n > 0:
            out.append((domain, 'BLOCKED', f'{fix_n} split/blocker-backed address(es) still require fixes'))
        elif proof_n > 0:
            out.append((domain, 'PROVING', f'{proof_n} address(es) still need direct canonical proof'))
        else:
            out.append((domain, 'READY', 'sampled addresses are directly proven and currently debt-free'))
    return out


def _domain_exit_criteria(rows: List[Tuple[str, Status, str]], fix_rows: List[Tuple[str, ...]], proof_rows: List[Tuple[str, ...]]) -> List[Tuple[str, str]]:
    readiness_map = {d: (r, reason) for d, r, reason in _domain_closure_readiness(rows, fix_rows, proof_rows)}
    out = []
    for domain, _status, _detail in rows:
        ready_state, ready_reason = readiness_map.get(domain, ('PROVING', 'still needs proof'))
        if ready_state == 'READY':
            out.append((domain, 'exit now: no sampled fix/proof debt remains'))
        else:
            out.append((domain, f'not ready: {ready_reason}'))
    return out


def _domain_exit_gaps(rows: List[Tuple[str, Status, str]], fix_rows: List[Tuple[str, ...]], proof_rows: List[Tuple[str, ...]]) -> List[Tuple[str, str, int, int]]:
    debt_map = {d: (f, p) for d, f, p in _domain_debt_totals(fix_rows, proof_rows)}
    out = []
    for domain, _status, _detail in rows:
        fix_n, proof_n = debt_map.get(domain, (0, 0))
        out.append((domain, 'fix' if fix_n else 'proof' if proof_n else 'clear', fix_n, proof_n))
    return out


def _domain_closure_queue(rows: List[Tuple[str, Status, str]], fix_rows: List[Tuple[str, ...]], proof_rows: List[Tuple[str, ...]]) -> List[Tuple[str, str, int, int, str, str]]:
    readiness_map = {d: (r, reason) for d, r, reason in _domain_closure_readiness(rows, fix_rows, proof_rows)}
    out = []
    for domain, _status, _detail in rows:
        d_fix = [row for row in fix_rows if _domain_for_address(row[0]) == domain]
        d_proof = [row for row in proof_rows if _domain_for_address(row[0]) == domain]
        ready_state, ready_reason = readiness_map.get(domain, ('PROVING', 'still needs proof'))
        next_probe = str((d_fix[0] if d_fix else d_proof[0])[-2] or 'Run Triage') if (d_fix or d_proof) else 'Re-run Triage'
        out.append((domain, ready_state, len(d_fix), len(d_proof), ready_reason, next_probe))
    return out


def _domain_proof_checklist(rows: List[Tuple[str, Status, str]], fix_rows: List[Tuple[str, ...]], proof_rows: List[Tuple[str, ...]]) -> List[Tuple[str, str]]:
    out = []
    for domain, _status, _detail in rows:
        d_fix = [row for row in fix_rows if _domain_for_address(row[0]) == domain]
        d_proof = [row for row in proof_rows if _domain_for_address(row[0]) == domain]
        if d_fix:
            out.append((domain, 'clear blocker-backed split rows first'))
        elif d_proof:
            out.append((domain, 'gather direct proof for inferred/default-backed rows'))
        else:
            out.append((domain, 'no sampled proof debt remains'))
    return out


def _domain_action(domain: str, fix_n: int, proof_n: int) -> str:
    if fix_n > 0:
        return 'fix'
    if proof_n > 0:
        return 'prove'
    return 'close'


__all__ = [name for name in globals() if ((name.startswith("_") and not name.startswith("__")) or name in {"Status", "TRIAGE_ADDRESS_MATRIX", "build_triage_rows", "first_non_open_domain", "first_non_open_address", "render_triage_report"})]
