from __future__ import annotations

"""Canonical triage summary.

Purpose:
- give a single, opinionated OPEN / SPLIT / CLOSED view from the canonical checkpoint
- speak in terms of canonical domains instead of scattered probe names
- surface next actions without reintroducing legacy identifiers as live targets
- group proof debt by canonical probe so triage yields a concrete action plan
"""

from collections import OrderedDict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.project_diagnostics import (
    diagnose_project,
    layer_wiring_inspector,
    preview_export_parity_probe,
    surface_mapping_inspector,
)
from app.project_model import get_surface_spec
from app.app_identity import APP_ID
from runtime.canonical_addr import canonical_registry
from runtime.resolver import resolve_address

Status = str

TRIAGE_ADDRESS_MATRIX: List[str] = [
    "project.surface.kind",
    "project.surface.count",
    "project.surface.width",
    "project.surface.height",
    "project.surface.mapping.serpentine",
    "project.postfx.trail_amount",
    "project.postfx.bleed_amount",
    "project.postfx.bleed_radius",
    "project.spatial.enabled",
    "project.spatial.world_scale",
]

from app.triage_report_build import (
    build_triage_rows,
    first_non_open_domain,
    first_non_open_address,
    _address_triage_rows,
    _domain_for_address,
    _merge_status,
)
from app.triage_report_metrics import (
    _count_by_confidence,
    _count_by_status,
    _probe_outcome_hint,
    _proof_class_for_row,
)
from app.triage_report_debt import (
    _domain_action,
    _domain_closure_candidates,
    _domain_closure_queue,
    _domain_closure_readiness,
    _domain_debt_totals,
    _domain_execution_state,
    _domain_exit_criteria,
    _domain_exit_gaps,
    _domain_proof_checklist,
    _fix_debt_rows,
    _grouped_probe_plan,
    _grouped_reason_plan,
    _proof_debt_rows,
)
from app.triage_report_closure import *
from app.triage_report_closure_state import (
    _closure_decisions,
    _closure_ledger,
    _domain_closure_certificates,
    _previous_closed_domains,
    _store_closed_domains,
)
from app.triage_report_closure_session import (
    _closure_session_plan,
    _closure_workset,
    _execution_pack_from_session,
    _execution_pack_receipt,
    _reevaluation_gate,
    _reevaluation_transition,
)
from app.triage_report_closure_declaration import (
    _all_doors_open_declaration,
    _all_doors_open_readiness,
    _auto_closure_control,
)
from app.triage_report_delta import (
    _apply_probe_results,
    _load_probe_results,
    _probe_result_summary,
    _stability_summary,
    _store_execution_pack,
    _store_triage_baseline,
    _triage_delta,
)



def _canonical_row(row: Any) -> Tuple[Any, ...]:
    """Normalize triage/debt rows to the canonical 15-field address schema.

    Some triage pipelines append a probe hint as a 16th field. Reporting paths
    should tolerate both shapes and always unpack the canonical 15-field prefix.
    """
    if isinstance(row, tuple):
        return row[:15]
    if isinstance(row, list):
        return tuple(row[:15])
    return tuple(row)[:15] if isinstance(row, Iterable) and not isinstance(row, (str, bytes, dict)) else (row,)
def render_triage_report(project: Dict[str, Any], runtime: Optional[Dict[str, Any]] = None) -> str:
    if callable(project):
        try:
            project = project()
        except Exception:
            project = {}
    if callable(runtime):
        try:
            runtime = runtime()
        except Exception:
            runtime = {}
    project = project if isinstance(project, dict) else {}
    runtime = runtime if isinstance(runtime, dict) else {}
    rows = build_triage_rows(project if isinstance(project, dict) else {}, runtime)
    probe_results = _load_probe_results(project if isinstance(project, dict) else {})
    overall = "OPEN"
    for _domain, status, _detail in rows:
        overall = _merge_status(overall, status)

    address_rows = _address_triage_rows(project, runtime)
    fix_rows = _fix_debt_rows(address_rows)
    proof_rows = _proof_debt_rows(address_rows)

    lines: List[str] = []
    lines.append("== TRIAGE  ==")
    lines.append(f"overall: {overall}")
    lines.append("")
    lines.append("-- Door Status --")
    for domain, status, detail in rows:
        lines.append(f"- {domain}: {status}")
        if detail:
            lines.append(f"  {detail}")

    lines.append("")
    lines.append("-- Immediate Focus --")
    first = first_non_open_domain(rows)
    if first is None:
        lines.append("- All reported doors are OPEN.")
        lines.append("- Next: keep using triage as the single diagnosis path and expand the inspector rather than adding duplicate probes.")
    else:
        domain, status, detail = first
        lines.append(f"- First non-OPEN domain: {domain} ({status})")
        if detail:
            lines.append(f"  detail: {detail}")
        lines.append(f"  next: {_domain_action(domain, len([r for r in fix_rows if _domain_for_address(r[0]) == domain]), len([r for r in proof_rows if _domain_for_address(r[0]) == domain]))}")
        fix_debt = fix_rows
        proof_debt = proof_rows
        debt = fix_debt or proof_debt
        focus_addr = debt[0] if debt else first_non_open_address(project, runtime)
        if focus_addr is not None:
            addr, astatus, source, _scope, support, authored, preview, export, runtime_txt, writable, blocker, evidence, confidence, reason, probe = focus_addr
            lines.append(f"- First triage focus address: {addr} ({astatus})")
            lines.append(
                f"  source={source}; support={support}; authored={authored}; preview={preview}; export={export}; runtime={runtime_txt}; writable={writable}; blocker={blocker}; reason={reason}; evidence={evidence}; confidence={confidence}; probe={probe}"
            )

    address_rows = _address_triage_rows(project, runtime)
    fix_rows = fix_rows
    proof_rows = proof_rows
    previous_baseline = ((project.get("ui") or {}).get("triage_baseline") if isinstance(project, dict) else None)
    delta = _triage_delta(previous_baseline, address_rows)

    lines.append("")
    lines.append("-- Probe Result Ingest --")
    if not probe_results:
        lines.append("- none; triage is currently using inferred/runtime evidence only")
    else:
        lines.append("- triage applied stored probe outcomes from project.ui.triage_probe_results")
        for probe_name, result in list((_probe_result_summary(probe_results) or {}).items())[:12]:
            lines.append(f"- {probe_name}: result={result}")

    lines.append("")
    lines.append("-- Triage Delta --")
    if not delta.get("baseline_present"):
        lines.append("- no previous baseline; current triage snapshot will become the comparison point after this run")
    else:
        lines.append(f"- regressions: {len(delta.get('regressions') or [])}")
        lines.append(f"- improvements: {len(delta.get('improvements') or [])}")
        lines.append(f"- debt added: {len(delta.get('added_debt') or [])}")
        lines.append(f"- debt removed: {len(delta.get('removed_debt') or [])}")
        lines.append(f"- confidence up: {len(delta.get('confidence_up') or [])}")
        lines.append(f"- confidence down: {len(delta.get('confidence_down') or [])}")
        for label, items in (("regressed", delta.get('regressions') or []), ("improved", delta.get('improvements') or []), ("debt_added", delta.get('added_debt') or []), ("debt_removed", delta.get('removed_debt') or [])):
            if items:
                lines.append(f"- {label}: {', '.join(items[:6])}")

    lines.append("")
    lines.append("-- Triage Scoreboard --")
    status_counts = _count_by_status(address_rows)
    conf_counts = _count_by_confidence(address_rows)
    lines.append(f"- addresses: OPEN={status_counts.get('OPEN',0)} SPLIT={status_counts.get('SPLIT',0)} CLOSED={status_counts.get('CLOSED',0)}")
    lines.append(f"- debt: fix={len(fix_rows)} proof={len(proof_rows)}")
    lines.append(f"- confidence: direct={conf_counts.get('direct',0)} partial={conf_counts.get('partial',0)} inferred={conf_counts.get('inferred',0)} low={conf_counts.get('low',0)}")

    lines.append("")
    lines.append("-- Domain Debt Totals --")
    domain_totals = _domain_debt_totals(fix_rows, proof_rows)
    exit_map = {d: txt for d, txt in _domain_exit_criteria(rows, fix_rows, proof_rows)}
    if not domain_totals:
        lines.append("- none; no sampled fix/proof debt remains")
    else:
        for domain, fix_n, proof_n in domain_totals:
            lines.append(f"- {domain}: fix={fix_n} proof={proof_n}")

    lines.append("")
    lines.append("-- Domain Closure Readiness --")
    for domain, readiness, reason in _domain_closure_readiness(rows, fix_rows, proof_rows):
        lines.append(f"- {domain}: {readiness}")
        lines.append(f"  reason: {reason}")
        lines.append(f"  exit: {exit_map.get(domain, 're-run triage')}")

    lines.append("")
    lines.append("-- Domain Exit Gaps --")
    for domain, gap_kind, fix_n, proof_n in _domain_exit_gaps(rows, fix_rows, proof_rows):
        lines.append(f"- {domain}:")
        lines.append(f"  gap={gap_kind}; fix={fix_n}; proof={proof_n}")

    lines.append("")
    lines.append("-- Domain Proof Checklist --")
    for domain, item in _domain_proof_checklist(rows, fix_rows, proof_rows):
        lines.append(f"- {domain}:")
        lines.append(f"  {item}")

    lines.append("")
    lines.append("-- Domain Closure Execution --")
    lines.append("- domains move from ACTIVE_FIX / ACTIVE_PROOF to CLOSED as sampled debt is cleared with direct canonical proof")
    for domain, state, why, next_probe in _domain_execution_state(rows, fix_rows, proof_rows):
        lines.append(f"- {domain}: {state}; next_probe={next_probe}")
        lines.append(f"  why: {why}")
        lines.append(f"  exit: {exit_map.get(domain, 're-run triage')}")

    lines.append("")
    lines.append("-- Closure Candidates --")
    candidates = _domain_closure_candidates(rows, fix_rows, proof_rows, delta)
    if not candidates:
        lines.append("- none yet; keep working the closure queue until a domain reaches READY with no sampled debt or regressions")
    else:
        for domain, note in candidates:
            lines.append(f"- {domain}: {note}")

    lines.append("")
    lines.append("-- Closure Certificates --")
    certificates = _domain_closure_certificates(rows, fix_rows, proof_rows, delta, address_rows)
    if not certificates:
        lines.append("- none yet; no domain is ready to close as a closure candidate")
    else:
        for domain, proof, regress, exit_txt in certificates:
            lines.append(f"- {domain}:")
            lines.append(f"  proof: {proof}")
            lines.append(f"  delta: {regress}")
            lines.append(f"  close_if: {exit_txt}")

    previous_closed = _previous_closed_domains(project)
    current_closed = [domain for domain, _note in candidates if 'ready to close now' in _note]
    ledger_rows = _closure_ledger(previous_closed, current_closed, rows, fix_rows, proof_rows, delta)
    _store_closed_domains(project, current_closed)

    lines.append("")
    lines.append("-- Closure Ledger --")
    if not ledger_rows:
        lines.append("- none yet; no domains have been closed or reopened")
    else:
        for domain, state, why in ledger_rows:
            lines.append(f"- {domain}: {state}")
            lines.append(f"  why: {why}")

    lines.append("")
    lines.append("-- Closure Decisions --")
    decisions = _closure_decisions(rows, fix_rows, proof_rows, delta, address_rows, ledger_rows)
    for domain, action, why, gate in decisions:
        lines.append(f"- {domain}: {action}")
        lines.append(f"  why: {why}")
        lines.append(f"  gate: {gate}")

    lines.append("")
    lines.append("-- Closure Session --")
    session = _closure_session_plan(rows, fix_rows, proof_rows, decisions)
    if not session:
        lines.append("- no active closure session; sampled domains are closed or ready to close")
    else:
        lines.append(f"- domain: {session['domain']} ({session['action']})")
        lines.append(f"  why: {session['why']}")
        lines.append(f"  run_probe: {session['probe']}")
        lines.append(f"  close_gate: {session['gate']}")
        if not session['addresses']:
            lines.append("  addresses: none sampled; verify the domain-level probe before freezing")
        else:
            for row in session['addresses']:
                addr, status, source, scope, support, authored, preview, export, runtime_txt, writable, blocker, evidence, confidence, reason, probe = _canonical_row(row)
                lines.append(f"  {addr} -> {status} / {reason}; confidence={confidence}; probe={probe}")

    lines.append("")
    lines.append("-- Closure Workset --")
    workset = _closure_workset(rows, fix_rows, proof_rows, decisions)
    if not workset:
        lines.append("- no active closure workset; all sampled domains are either closed or ready to close")
    else:
        for domain, action, why, gate, items in workset:
            lines.append(f"- {domain}: {action}")
            lines.append(f"  why: {why}")
            lines.append(f"  gate: {gate}")
            if not items:
                lines.append("  addresses: none sampled in debt for this domain; verify domain-level probe before freezing")
            else:
                for row in items:
                    addr, status, source, scope, support, authored, preview, export, runtime_txt, writable, blocker, evidence, confidence, reason, probe = _canonical_row(row)
                    lines.append(f"  {addr} -> {status} / {reason}; confidence={confidence}; probe={probe}")

    execution_pack = _execution_pack_from_session(session, rows, fix_rows, proof_rows)

    lines.append("")
    lines.append("-- Execution Pack --")
    if not execution_pack:
        lines.append("- none; no current closure session is active")
    else:
        lines.append(f"- domain: {execution_pack['domain']}")
        lines.append(f"  decision: {execution_pack['decision']}")
        lines.append(f"  probe: {execution_pack['probe']}")
        lines.append(f"  addresses: {', '.join(execution_pack['addresses']) if execution_pack['addresses'] else 'none'}")
        lines.append(f"  close_with: {execution_pack['close_with']}")
        lines.append(f"  reason_codes: {', '.join(execution_pack['reason_codes']) if execution_pack['reason_codes'] else 'none'}")
        lines.append(f"  session_outcome_target: {execution_pack['session_outcome_target']}")

    execution_receipt = _execution_pack_receipt(execution_pack, probe_results)
    reevaluation_gate = _reevaluation_gate(execution_pack, execution_receipt)
    reevaluation_transition = _reevaluation_transition(execution_pack, execution_receipt, reevaluation_gate, workset)
    stability_summary = _stability_summary(address_rows, candidates, execution_pack)
    auto_control_rows, auto_closed = _auto_closure_control(project, decisions, execution_receipt, reevaluation_transition, stability_summary)

    lines.append("")
    lines.append("-- Reevaluation Gate --")
    if not reevaluation_gate:
        lines.append("- none; no active execution pack to evaluate")
    else:
        lines.append(f"- state: {reevaluation_gate['state']}")
        lines.append(f"  next: {reevaluation_gate['next']}")
        lines.append(f"  summary: {reevaluation_gate['summary']}")

    lines.append("")
    lines.append("-- Execution Receipt --")
    if not execution_receipt:
        lines.append("- none; no current execution pack is active")
    else:
        lines.append(f"- state: {execution_receipt['state']}")
        lines.append(f"  summary: {execution_receipt['summary']}")
        if execution_receipt['touched']:
            for addr, result, probe_name in execution_receipt['touched'][:8]:
                lines.append(f"  {addr} -> result={result}; probe={probe_name}")

    lines.append("")
    lines.append("-- Reevaluation Transition --")
    if not reevaluation_transition:
        lines.append("- none; no active transition to advance from the current execution state")
    else:
        lines.append(f"- action: {reevaluation_transition['action']}")
        lines.append(f"  from_session: {reevaluation_transition['from_session']}")
        lines.append(f"  next_domain: {reevaluation_transition['next_domain']}")
        lines.append(f"  next_probe: {reevaluation_transition['next_probe']}")
        lines.append(f"  next_addresses: {', '.join(reevaluation_transition['next_addresses']) if reevaluation_transition['next_addresses'] else 'none'}")
        lines.append(f"  transition_reason: {reevaluation_transition['transition_reason']}")

    lines.append("")
    lines.append("-- Stability Summary --")
    stable_items = stability_summary.get('stable_to_close') or []
    watch_items = stability_summary.get('watchlist') or []
    reopen_items = stability_summary.get('reopen_now') or []
    lines.append(f"- stable_to_close: {', '.join(d for d, _why in stable_items) if stable_items else 'none'}")
    if stable_items:
        for domain, why in stable_items:
            lines.append(f"  {domain}: {why}")
    lines.append(f"- watchlist: {', '.join(d for d, _why in watch_items) if watch_items else 'none'}")
    if watch_items:
        for domain, why in watch_items[:8]:
            lines.append(f"  {domain}: {why}")
    lines.append(f"- reopen_now: {', '.join(d for d, _why in reopen_items) if reopen_items else 'none'}")
    if reopen_items:
        for domain, why in reopen_items:
            lines.append(f"  {domain}: {why}")

    lines.append("")
    lines.append("-- Domain Auto-Close / Auto-Reopen --")
    if not auto_control_rows:
        lines.append("- no automatic closure-control changes this run")
    else:
        for domain, action, why, gate in auto_control_rows:
            lines.append(f"- {domain}: {action}")
            lines.append(f"  why: {why}")
            lines.append(f"  gate: {gate}")
    lines.append(f"- closed_domains: {', '.join(auto_closed) if auto_closed else 'none'}")

    all_doors = _all_doors_open_readiness(rows, decisions, auto_closed, stability_summary, delta)

    lines.append("")
    lines.append("-- All Doors Open Readiness --")
    lines.append(f"- state: {all_doors['state']}")
    lines.append(f"- closed_domains: {len(all_doors['closed_domains'])}/{all_doors['total_domains']}")
    lines.append(f"- blocker: {all_doors['blocker']}")
    lines.append(f"- next: {all_doors['next_step']}")
    if all_doors['stable_to_close']:
        lines.append(f"- stable_to_close: {', '.join(all_doors['stable_to_close'])}")
    if all_doors['blocked_domains']:
        lines.append(f"- blocked_domains: {', '.join(all_doors['blocked_domains'])}")
    if all_doors['proving_domains']:
        lines.append(f"- proving_domains: {', '.join(all_doors['proving_domains'])}")

    declaration = _all_doors_open_declaration(all_doors, decisions, certificates, ledger_rows)

    lines.append("")
    lines.append("-- All Doors Open Declaration --")
    lines.append(f"- decision: {declaration['decision']}")
    lines.append(f"- why: {declaration['why']}")
    if declaration['manifest']:
        lines.append("- manifest:")
        for domain, proof, regress, exit_txt, ledger_state, ledger_why in declaration['manifest']:
            lines.append(f"  {domain}: proof={proof}; delta={regress}; close_if={exit_txt}; ledger={ledger_state} ({ledger_why})")
    if declaration['holdouts']:
        lines.append("- holdouts:")
        for domain, reason, next_txt in declaration['holdouts']:
            lines.append(f"  {domain}: reason={reason}; next={next_txt}")

    lines.append("")
    lines.append("-- Closure Queue --")
    lines.append("- next domains to close, ordered by blocked/proving state and remaining debt")
    for domain, readiness, fix_n, proof_n, reason, next_probe in _domain_closure_queue(rows, fix_rows, proof_rows):
        lines.append(f"- {domain}: {readiness}; fix={fix_n}; proof={proof_n}; next_probe={next_probe}")
        lines.append(f"  reason: {reason}")
        lines.append(f"  exit: {exit_map.get(domain, 're-run triage')}")

    lines.append("")
    lines.append("-- Per-Domain Next --")
    for domain, status, _detail in rows:
        lines.append(f"- {domain}: {_domain_action(domain, len([r for r in fix_rows if _domain_for_address(r[0]) == domain]), len([r for r in proof_rows if _domain_for_address(r[0]) == domain]))}")

    lines.append("")
    lines.append("-- Fix Debt --")
    if not fix_rows:
        lines.append("- none; no sampled addresses are clearly broken")
    else:
        for row in fix_rows[:12]:
            addr, status, source, scope, support, authored, preview, export, runtime_txt, writable, blocker, evidence, confidence, reason, probe = _canonical_row(row)
            lines.append(f"- {addr}: {status} / {reason}")
            lines.append(
                f"  source={source}; scope={scope or 'unknown'}; support={support}; blocker={blocker}; confidence={confidence}; probe={probe}"
            )

    lines.append("")
    lines.append("-- Proof Debt --")
    proof_rows = proof_rows
    if not proof_rows:
        lines.append("- none; all sampled addresses are OPEN with direct confidence")
    else:
        for row in proof_rows[:12]:
            addr, status, source, scope, support, authored, preview, export, runtime_txt, writable, blocker, evidence, confidence, reason, probe = _canonical_row(row)
            lines.append(f"- {addr}: {status} / {reason}")
            lines.append(
                f"  source={source}; scope={scope or 'unknown'}; support={support}; blocker={blocker}; confidence={confidence}; probe={probe}"
            )

    lines.append("")
    lines.append("-- Action Plan --")
    lines.append("- grouped by recommended canonical probe so triage yields one concrete next move per probe cluster")
    grouped_plan = _grouped_probe_plan(fix_rows, proof_rows)
    if not grouped_plan:
        lines.append("- none; there is no remaining sampled proof debt")
    else:
        for probe, items in grouped_plan[:8]:
            lines.append(f"- {probe}: {len(items)} item(s)")
            for row in items[:4]:
                addr, status, source, scope, support, authored, preview, export, runtime_txt, writable, blocker, evidence, confidence, reason, _probe = _canonical_row(row)
                lines.append(
                    f"  {addr} -> {status} / {reason}; source={source}; blocker={blocker}; support={support}"
                )
            if len(items) > 4:
                lines.append(f"  ... plus {len(items) - 4} more")

    lines.append("")
    lines.append("-- Reason Clusters --")
    lines.append("- grouped by debt reason so systemic parity failures surface together")
    grouped_reasons = _grouped_reason_plan(fix_rows, proof_rows)
    if not grouped_reasons:
        lines.append("- none; there is no remaining sampled fix/proof debt")
    else:
        for reason, items in grouped_reasons[:8]:
            domains = sorted({_domain_for_address(row[0]) for row in items})
            lines.append(f"- {reason}: {len(items)} item(s) across {', '.join(domains)}")
            for row in items[:4]:
                addr, status, source, scope, support, authored, preview, export, runtime_txt, writable, blocker, evidence, confidence, _reason, probe = _canonical_row(row)
                lines.append(
                    f"  {addr} -> {status}; source={source}; blocker={blocker}; confidence={confidence}; probe={probe}"
                )
            if len(items) > 4:
                lines.append(f"  ... plus {len(items) - 4} more")

    lines.append("")
    lines.append("-- Per-Address Status --")
    lines.append("- status is canonical diagnosis for the address itself")
    lines.append("- authored/preview/export/runtime show support parity by canonical address family")
    lines.append("- blocker explains the first concrete reason this address is not fully healthy")
    lines.append("- evidence shows what triage actually proved for the address")
    lines.append("- confidence distinguishes direct proof from inference or partial coverage")
    for _row in address_rows:
        addr, status, source, scope, support, authored, preview, export, runtime_txt, writable, blocker, evidence, confidence, reason, probe = _canonical_row(_row)
        lines.append(f"- {addr}: {status}")
        proof_class = _proof_class_for_row((addr, status, source, scope, support, authored, preview, export, runtime_txt, writable, blocker, evidence, confidence, reason, probe))
        outcome = _probe_outcome_hint((addr, status, source, scope, support, authored, preview, export, runtime_txt, writable, blocker, evidence, confidence, reason, probe))
        lines.append(
            f"  source={source}; scope={scope or 'unknown'}; support={support}; authored={authored}; preview={preview}; export={export}; runtime={runtime_txt}; writable={writable}; blocker={blocker}; reason={reason}; evidence={evidence}; confidence={confidence}; proof_class={proof_class}; probe={probe}"
        )
        lines.append(f"  close_with: {outcome}")

    lines.append("")
    lines.append("-- Canonical Evidence --")
    sm = surface_mapping_inspector(project)
    for line in sm[:6]:
        lines.append(f"  {line}")
    lw = layer_wiring_inspector(project)
    lw_lines = [x for x in lw.splitlines() if x.strip()][:6]
    for line in lw_lines:
        lines.append(f"  {line}")

    lines.append("")
    lines.append("-- Next --")
    if overall == "OPEN":
        lines.append("- Canonical checkpoint is structurally healthy enough to move into richer triage UI and All Doors Open verification.")
        lines.append("- Next build should classify per-address source / support / gate status in the inspector, not keep sweeping residue.")
    elif overall == "SPLIT":
        lines.append("- Fix the first non-OPEN domain above before enabling new architectural layers.")
        lines.append("- Use Resolver Inspector on the first failing address/domain and remove the split path rather than adding compatibility.")
    else:
        lines.append("- Resolve CLOSED domains first; do not move on to era gating or showcase work yet.")
        lines.append("- Canonical geometry/resolver truth must be healthy before higher-level systems rely on it.")
    _store_closed_domains(project, [domain for domain, _note in candidates])
    _store_execution_pack(project, execution_pack)
    _store_triage_baseline(project, address_rows)
    return "\n".join(lines)
