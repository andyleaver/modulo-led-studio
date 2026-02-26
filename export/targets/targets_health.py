from __future__ import annotations

from typing import Any, Dict
from runtime.extensions_v1 import register_health_probe

from .registry import diagnose_target_packs

def _probe() -> Dict[str, Any]:
    info = diagnose_target_packs()
    # Keep output compact; UI can show full JSON on demand.
    return {
        "targets_ok": len(info.get("ok") or []),
        "targets_errors": len(info.get("errors") or []),
        "supported_v1": info.get("supported_v1") or [],
        "errors": info.get("errors") or [],
        "sample": (info.get("ok") or [])[:5],
    }

register_health_probe("targets", _probe)
