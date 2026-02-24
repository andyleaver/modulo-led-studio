#!/usr/bin/env python3
"""
Parity sweep: iterate all shipped effects vs all builtin targets and report export gating.

Outputs:
- parity_reports/parity_sweep_<timestamp>.csv
- parity_reports/parity_sweep_<timestamp>.md

This is intentionally non-invasive: it does NOT modify projects or targets.
"""
from __future__ import annotations

import csv
import argparse
import datetime as _dt
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure repo root on sys.path when run from anywhere
import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from export.targets.registry import list_targets, load_target
from export.gating import gate_project_for_target
from export.export_eligibility import get_eligibility, ExportStatus

CATALOG_PATH = REPO_ROOT / "behaviors" / "capabilities_catalog.json"

def _load_effect_keys() -> List[str]:
    import json
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    effects = data.get("effects") or {}
    if isinstance(effects, dict):
        return sorted(list(effects.keys()))
    if isinstance(effects, list):
        # legacy
        return sorted([e.get("key") for e in effects if isinstance(e, dict) and e.get("key")])
    return []

def _minimal_project_for_behavior(behavior_key: str) -> Dict[str, Any]:
    # Minimal project model the exporter/gater expects.
    return {
        "version": 1,
        # Keep this intentionally small so low-RAM targets (e.g. Arduino Uno)
        # don't warn purely due to the sweep harness.
        "layout": {"kind": "cells", "width": 8, "height": 8},
        "postfx": {},
        "layers": [
            {
                "name": behavior_key,
                "enabled": True,
                "behavior": behavior_key,
                "params": {},
                # export-safe surface defaults (if used by behavior)
                "purpose_f0": 0.0,
                "purpose_f1": 0.0,
                "purpose_i0": 0,
            }
        ],
    }

def main() -> int:
    if not CATALOG_PATH.exists():
        print(f"ERROR: missing catalog at {CATALOG_PATH}")
        return 2

    parser = argparse.ArgumentParser(description="Modulo export parity sweep")
    parser.add_argument("--out-dir", default=None, help="Directory to write reports (default: parity_reports/ or $MODULO_ARTIFACT_DIR)")
    parser.add_argument("--json-summary", action="store_true", help="Also write a small JSON summary next to the reports")
    args = parser.parse_args()

    effect_keys = _load_effect_keys()
    # NOTE: registry.list_targets() returns target *records* (dicts), not ids.
    # We normalize to ids here to avoid accidentally passing dicts to load_target().
    target_records = list_targets()
    target_ids = [t.get("id") if isinstance(t, dict) else str(t) for t in target_records]

    ts = _dt.datetime.utcnow().strftime("%Y%m%d_%H%M%SZ")
    base_dir = Path(os.environ.get("MODULO_ARTIFACT_DIR")) if os.environ.get("MODULO_ARTIFACT_DIR") else None
    if args.out_dir:
        out_dir = Path(args.out_dir)
    elif base_dir:
        out_dir = base_dir / "parity_reports"
    else:
        out_dir = REPO_ROOT / "parity_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"parity_sweep_{ts}.csv"
    md_path = out_dir / f"parity_sweep_{ts}.md"

    rows: List[Dict[str, Any]] = []
    totals = {"ok": 0, "warn": 0, "err": 0, "skip": 0, "blocked": 0}

    def _is_capability_missing_error(msg: str) -> bool:
        m = (msg or "").lower()
        # "Skip" means: export is blocked only because the selected *target* lacks
        # a declared runtime capability (so it's not a regression in the app/effect).
        if "does not support" in m or "doesn't support" in m or "not support" in m:
            return True
        if "supports_postfx_runtime" in m or "supports_operators_runtime" in m:
            return True
        if m.startswith("postfx") or m.startswith("operators"):
            return True
        return False

    for tid in target_ids:
        if not tid:
            # Defensive: skip any malformed records.
            continue
        try:
            tmeta = load_target(tid).meta  # normalized meta dict
        except Exception as e:
            rows.append({
                "target": tid,
                "behavior": "*",
                "result": "ERR",
                "errors": f"Failed to load target pack: {e}",
                "warnings": "",
            })
            totals["err"] += 1
            continue
        for beh in effect_keys:
            elig = get_eligibility(beh)
            if elig.status != ExportStatus.EXPORTABLE:
                rows.append({
                    "target": tid,
                    "behavior": beh,
                    "result": elig.status,
                    "errors": elig.reason or "",
                    "warnings": "",
                })
                totals["blocked"] += 1
                continue

            proj = _minimal_project_for_behavior(beh)
            gate = gate_project_for_target(proj, tmeta)
            if gate.ok and not gate.errors and not gate.warnings:
                res = "ok"
                totals["ok"] += 1
            elif gate.ok and gate.warnings and not gate.errors:
                res = "warn"
                totals["warn"] += 1
            else:
                # Phase 6: distinguish real regressions (ERR) from "capability missing" SKIPs.
                errs = gate.errors or []
                if errs and all(_is_capability_missing_error(e) for e in errs):
                    res = "skip"
                    totals["skip"] += 1
                else:
                    res = "err"
                    totals["err"] += 1

            rows.append({
                "target": tid,
                "behavior": beh,
                "result": res,
                "errors": " | ".join(gate.errors or []),
                "warnings": " | ".join(gate.warnings or []),
            })

    # Write CSV
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["target","behavior","result","errors","warnings"])
        w.writeheader()
        w.writerows(rows)

    # Write markdown summary
    def _count(pred):
        return sum(1 for r in rows if pred(r))

    md = []
    md.append(f"# Parity Sweep Report ({ts})")
    md.append("")
    md.append(f"- Targets: **{len(target_ids)}**")
    md.append(f"- Effects: **{len(effect_keys)}**")
    md.append("")
    md.append("## Totals")
    md.append("")
    md.append(f"- ok: **{totals['ok']}**")
    md.append(f"- warn: **{totals['warn']}**")
    md.append(f"- skip (target capability missing): **{totals['skip']}**")
    md.append(f"- err: **{totals['err']}**")
    md.append(f"- blocked (non-exportable): **{totals['blocked']}**")
    md.append("")
    md.append("## Quick links")
    md.append("")
    md.append(f"- CSV: `{csv_path.relative_to(REPO_ROOT)}`")
    md.append("")
    md.append("## Top non-OK (first 50)")
    md.append("")
    top_err = [r for r in rows if r["result"] in ("err","blocked","skip")][:50]
    for r in top_err:
        md.append(f"- `{r['target']}` / `{r['behavior']}` → **{r['result']}** — {r['errors'] or r['warnings']}")
    md.append("")

    md_path.write_text("\n".join(md), encoding="utf-8")


if args.json_summary:
    summary_path = out_dir / f"parity_sweep_{ts}.summary.json"
    summary_path.write_text(json.dumps({
        "timestamp": ts,
        "targets": len(target_ids),
        "effects": len(effect_keys),
        "totals": totals,
        "csv": str(csv_path),
        "md": str(md_path),
    }, indent=2), encoding="utf-8")

    print(f"Wrote:\n- {csv_path}\n- {md_path}")

    # Exit non-zero only for real regressions.
    return 1 if totals["err"] > 0 else 0

if __name__ == "__main__":
    raise SystemExit(main())
