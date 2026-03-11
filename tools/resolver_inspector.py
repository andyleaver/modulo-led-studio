#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json
import os
from typing import Any, Dict, List

from app.project_manager import migrate_project_dict
from app.masks_resolver import resolve_target_mask_for_layer

def _load_project_from_path(path: str) -> Dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return migrate_project_dict(raw if isinstance(raw, dict) else {})

def _scan_shadow_keys(project: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    layers = project.get("layers") or []
    if isinstance(layers, list):
        for i, L0 in enumerate(layers):
            L = L0 if isinstance(L0, dict) else {}
            if "blend" in L:
                issues.append(f"layer[{i}] has shadow key 'blend'")
            if "blend_mode" not in L:
                issues.append(f"layer[{i}] missing 'blend_mode'")
    return issues

def main() -> int:
    # Use MODULO_PROJECT if provided, else try known local project locations, else fall back to a shipped fixture.
    repo_root = Path(__file__).resolve().parent.parent
    proj_path = os.environ.get("MODULO_PROJECT", "").strip()

    candidates = []
    if proj_path:
        candidates.append(Path(proj_path))
    candidates.append(repo_root / "user_data" / "last_project.json")
    candidates.append(repo_root / "fixtures" / "projects" / "order_pipeline_lock.json")

    p: Dict[str, Any] | None = None
    used = None
    for c in candidates:
        try:
            if c.is_file():
                p = _load_project_from_path(str(c))
                used = str(c)
                break
        except Exception:
            continue

    if p is None:
        p = {}
        used = "none"

    report: Dict[str, Any] = {
        "project_source": used,
        "shadow_key_issues": _scan_shadow_keys(p),
        "mask_resolution": [],
    }

    # best-effort: resolve UI target mask for each layer
    try:
        layers = p.get("layers") or []
        if isinstance(layers, list):
            for i, L0 in enumerate(layers):
                L = L0 if isinstance(L0, dict) else {}
                key, idxs = resolve_target_mask_for_layer(L, p, n=None)
                report["mask_resolution"].append({
                    "layer_index": i,
                    "mask_key": key,
                    "resolved_count": int(len(idxs)) if idxs is not None else 0,
                })
    except Exception as e:
        report["mask_resolution_error"] = str(e)

    # Write reports to external artifact storage by default so the repo stays clean.
    out_dir = os.environ.get("MODULO_ARTIFACT_DIR", "").strip()
    if out_dir:
        artifact_root = Path(out_dir)
    else:
        artifact_root = repo_root.parent / "artifacts" / "resolver_inspector"
    try:
        artifact_root.mkdir(parents=True, exist_ok=True)
        out_file = str(artifact_root / "resolver_inspector.json")
    except Exception:
        fallback_root = repo_root.parent / "artifacts" / "resolver_inspector"
        fallback_root.mkdir(parents=True, exist_ok=True)
        out_file = str(fallback_root / "resolver_inspector.json")

    try:
        Path(out_file).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(f"[resolver_inspector] wrote {out_file}")
    except Exception as e:
        print(f"[resolver_inspector] failed to write report: {e}")

    # Non-zero if shadow keys exist (hard fail signal for CI if desired)
    return 0 if len(report["shadow_key_issues"]) == 0 else 2

if __name__ == "__main__":
    raise SystemExit(main())
