"""Project round-trip probe.

Goal: prove authored project data can be serialized and reloaded without schema drift,
shadow keys, or unstable ordering.

This probe is intentionally conservative: it does not assume file IO; it operates on
in-memory dict-like project data.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

@dataclass
class ProbeResult:
    probe_id: str
    ok: bool
    summary: str
    evidence: Dict[str, Any]

def _canon_json(obj: Any) -> str:
    """Canonical JSON: stable key order, stable separators."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def _sha12(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]

def _find_shadow_keys(d: Any) -> List[str]:
    """Detect known shadow-key hazards recursively."""
    out: List[str] = []

    def walk(x: Any, path: str) -> None:
        if isinstance(x, dict):
            # Example shadow key pairs you already care about
            if "blend" in x and "blend_mode" in x:
                out.append(path + ": has both blend and blend_mode")
            for k, v in x.items():
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]")

    walk(d, "")
    return out

def run_project_roundtrip_probe(project: Dict[str, Any]) -> ProbeResult:
    """Run round-trip probe on an in-memory project dict."""
    probe_id = "P4.PROJECT_ROUNDTRIP_IDENTITY"

    # Canonicalize input
    j1 = _canon_json(project)
    h1 = _sha12(j1)

    # Round-trip through json parse
    reloaded = json.loads(j1)
    j2 = _canon_json(reloaded)
    h2 = _sha12(j2)

    shadows = _find_shadow_keys(reloaded)

    ok = (j1 == j2) and (len(shadows) == 0)
    summary = "PASS" if ok else "FAIL"

    evidence: Dict[str, Any] = {
        "hash_before": h1,
        "hash_after": h2,
        "same_canonical_json": (j1 == j2),
        "shadow_key_warnings": shadows[:20],
        "shadow_key_count": len(shadows),
        "size_before": len(j1),
        "size_after": len(j2),
    }

    if not ok:
        # Provide a short hint only (don’t dump full JSON)
        if j1 != j2:
            evidence["diff_hint"] = "Canonical JSON differs after parse+serialize; schema drift or non-JSON-safe types."
        if shadows:
            evidence["diff_hint2"] = "Shadow keys detected; remove ambiguous keys (e.g., blend vs blend_mode)."

    return ProbeResult(
        probe_id=probe_id,
        ok=ok,
        summary=summary,
        evidence=evidence,
    )

def format_probe_result(res: ProbeResult) -> str:
    lines = []
    lines.append(f"{res.probe_id}: {res.summary}")
    lines.append(json.dumps(res.evidence, indent=2, sort_keys=False))
    return "\n".join(lines) + "\n"
