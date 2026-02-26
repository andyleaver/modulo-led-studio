"""Project export validation used by the UI.

Why this exists:
  - The UI wants a *list of problems* it can show as a checklist.
  - The exporter itself must still fail loudly (raises) even if the UI is bypassed.

So: `check_project()` returns a list[str] (empty == OK).
"""

from __future__ import annotations

from typing import List


def check_project(project: dict) -> List[str]:
    """Return a list of blocking issues for exporting this project.

    Single source of truth:
      - exporter-owned parity summary (export/parity_summary.py)
    """
    problems: List[str] = []

    # 0) Structural validation (zones/groups/masks/target_mask)
    try:
        from app.project_validation import validate_project
        ok2, probs2 = validate_project(project or {})
        if not ok2:
            problems.extend([str(x) for x in (probs2 or []) if str(x).strip()])
    except Exception:
        problems.append('Unable to validate zones/groups/masks structure.')

    # 1) Exporter-owned parity summary (single source of truth)
    try:
        from export.parity_summary import compute_export_parity_summary
        # Use selected export target meta so budget/limits match the chosen board/pack.
        tid = ''
        try:
            ex = (project or {}).get('export') or {}
            if isinstance(ex, dict) and ex.get('target_id'):
                tid = str(ex.get('target_id'))
        except Exception:
            tid = ''
        tmeta = {}
        if tid:
            try:
                from export.targets.registry import load_target
                t = load_target(tid)
                tmeta = dict(getattr(t, 'meta', None) or {})
            except Exception:
                tmeta = {}
        summ = compute_export_parity_summary(project or {}, tmeta)
        problems.extend([str(e) for e in (summ.errors or []) if str(e).strip()])
    except Exception:
        # If parity cannot be computed, block export (safer).
        problems.append('Unable to compute exporter parity summary.')

    # De-dup while preserving order.
    out: List[str] = []
    seen = set()
    for p in problems:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return out
