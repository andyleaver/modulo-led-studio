from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from app.triage_report_build import *
from app.project_apply import apply_project_root
from app.triage_report_closure_state import _previous_closed_domains, _store_closed_domains
from app.triage_report_delta import _store_closure_basis_map


def _auto_closure_control(project, decisions, execution_receipt, reevaluation_transition, stability_summary):
    """Automatically close or reopen domains from current triage conditions.

    A stability window keeps domains from flapping on weak or partial evidence.
    Domains close only after consecutive stable runs, and reopen only on real
    regression or blocker evidence.
    """
    prev = _previous_closed_domains(project)
    prev_set = set(prev)
    closed = set(prev)
    rows = []
    stable_domains = {str(domain) for domain, _why in ((stability_summary or {}).get('stable_to_close') or [])}
    reopen_domains = {str(domain) for domain, _why in ((stability_summary or {}).get('reopen_now') or [])}
    watchlist = {str(domain) for domain, _why in ((stability_summary or {}).get('watchlist') or [])}
    for domain, action, why, gate in decisions:
        if action in ('CLOSE_NOW', 'KEEP_CLOSED'):
            if domain in stable_domains:
                was_closed = domain in prev_set
                closed.add(domain)
                rows.append((domain, 'AUTO_CLOSE' if not was_closed else 'AUTO_KEEP_CLOSED', why, gate))
            elif domain in watchlist:
                rows.append((domain, 'WATCHLIST', why, gate))
        elif action == 'REOPEN':
            if domain in closed:
                closed.discard(domain)
            rows.append((domain, 'AUTO_REOPEN', why, gate))
        elif domain in prev_set and domain in reopen_domains:
            closed.discard(domain)
            rows.append((domain, 'AUTO_REOPEN', why, gate))
        elif domain in prev_set and action == 'HOLD_PROVING':
            rows.append((domain, 'AUTO_KEEP_CLOSED', 'reopen guard held; no real regression detected', gate))
    if execution_receipt and str(execution_receipt.get('state') or '') in ('PARTIAL_WITH_FAILURE', 'BLOCKED_BY_RESULT') and reevaluation_transition:
        dom = str(reevaluation_transition.get('next_domain') or '')
        if dom and dom in closed:
            closed.discard(dom)
            rows.append((dom, 'AUTO_REOPEN', 'failed execution receipt for active session', reevaluation_transition.get('transition_reason') or 'investigate failures'))
    ordered = sorted(closed)
    _store_closed_domains(project, ordered)
    _store_closure_basis_map(project, (stability_summary or {}).get('basis_map') or {})
    if isinstance(project, dict):
        ui0 = project.get('ui')
        ui = dict(ui0) if isinstance(ui0, dict) else {}
        ui['triage_auto_closed_domains'] = ordered
        p2, _validation, _changes = apply_project_root(project, 'ui', ui)
        project.clear()
        project.update(p2)
    return rows, ordered

def _all_doors_open_readiness(rows, decisions, auto_closed, stability_summary, delta):
    domain_names = [str(domain) for domain, _status, _detail in (rows or []) if domain]
    total_domains = len(domain_names)
    closed = set(str(x) for x in (auto_closed or []) if x)
    decision_map = {str(domain): str(action) for domain, action, _why, _gate in (decisions or [])}
    stable = [str(domain) for domain, _why in ((stability_summary or {}).get('stable_to_close') or []) if domain]
    watch = [str(domain) for domain, _why in ((stability_summary or {}).get('watchlist') or []) if domain]
    reopen = [str(domain) for domain, _why in ((stability_summary or {}).get('reopen_now') or []) if domain]
    regressions = list(delta.get('regressions') or []) if isinstance(delta, dict) else []

    blocked = [d for d in domain_names if decision_map.get(d) in ('HOLD_BLOCKED', 'REOPEN')]
    proving = [d for d in domain_names if decision_map.get(d) == 'HOLD_PROVING']

    if total_domains > 0 and len(closed) == total_domains and not blocked and not proving and not regressions:
        state = 'VERIFIED'
        blocker = 'none'
        next_step = 'all sampled domains are closed and no current regression blocks All Doors Open'
    elif not blocked and not regressions and total_domains > 0 and len(closed) + len(stable) >= total_domains:
        state = 'NEAR_READY'
        blocker = 'stability window not yet complete for one or more domains'
        next_step = 'rerun triage after another stable run and let remaining stable_to_close domains close automatically'
    else:
        state = 'NOT_READY'
        blocker_bits = []
        if blocked:
            blocker_bits.append('blocked=' + ', '.join(blocked[:4]))
        if proving:
            blocker_bits.append('proving=' + ', '.join(proving[:4]))
        if regressions:
            blocker_bits.append(f'regressions={len(regressions)}')
        if reopen:
            blocker_bits.append('reopen_now=' + ', '.join(reopen[:4]))
        blocker = '; '.join(blocker_bits) if blocker_bits else 'domains still active'
        if blocked:
            next_step = 'work the first blocked domain from the closure queue until it leaves HOLD_BLOCKED/REOPEN'
        elif proving:
            next_step = 'complete direct proof for the first proving domain and rerun triage'
        else:
            next_step = 'continue closure sessions and rerun triage until all domains are closed'

    return {
        'state': state,
        'total_domains': total_domains,
        'closed_domains': sorted(closed),
        'stable_to_close': stable,
        'watchlist': watch,
        'reopen_now': reopen,
        'blocked_domains': blocked,
        'proving_domains': proving,
        'regressions': regressions,
        'blocker': blocker,
        'next_step': next_step,
    }

def _all_doors_open_declaration(all_doors, decisions, certificates, ledger_rows):
    all_doors = all_doors or {}
    state = str(all_doors.get('state') or 'NOT_READY')
    closed_domains = [str(x) for x in (all_doors.get('closed_domains') or []) if x]
    blocked_domains = [str(x) for x in (all_doors.get('blocked_domains') or []) if x]
    proving_domains = [str(x) for x in (all_doors.get('proving_domains') or []) if x]
    regressions = list(all_doors.get('regressions') or [])
    certificate_map = {str(domain): (proof, regress, exit_txt) for domain, proof, regress, exit_txt in (certificates or [])}
    ledger_map = {str(domain): (state_txt, why) for domain, state_txt, why in (ledger_rows or [])}
    if state == 'VERIFIED':
        decision = 'DECLARE_ALL_DOORS_OPEN'
        why = 'all sampled domains are closed with no active blocked/proving domains or regressions'
        manifest = []
        for domain in closed_domains:
            proof, regress, exit_txt = certificate_map.get(domain, ('closed domain', 'no regressions reported', 'keep triage stable'))
            ledger_state, ledger_why = ledger_map.get(domain, ('still_closed', 'closure ledger confirms domain is still closed'))
            manifest.append((domain, proof, regress, exit_txt, ledger_state, ledger_why))
        holdouts = []
    elif state == 'NEAR_READY':
        decision = 'HOLD_FOR_STABILITY'
        why = 'remaining domains still need the stability window to complete before declaration'
        manifest = []
        holdouts = [(domain, 'stability_window', 'rerun triage after another stable run') for domain in (all_doors.get('stable_to_close') or [])]
        if not holdouts:
            holdouts = [(domain, 'proving', 'complete final direct proof and rerun triage') for domain in proving_domains]
    else:
        decision = 'BLOCK_DECLARATION'
        why = str(all_doors.get('blocker') or 'domains still active')
        manifest = []
        holdouts = []
        for domain in blocked_domains:
            holdouts.append((domain, 'blocked', 'work the blocked domain from the closure queue'))
        for domain in proving_domains:
            holdouts.append((domain, 'proving', 'complete direct proof and rerun triage'))
        if regressions:
            holdouts.append(('regressions', f'{len(regressions)} active', 'investigate regressions before declaration'))
    return {
        'decision': decision,
        'why': why,
        'manifest': manifest,
        'holdouts': holdouts,
    }
