from __future__ import annotations

from typing import Any, Dict, List, Tuple


def validate_target_pack(meta: Any) -> Tuple[bool, List[str]]:
    """
    Validate a loaded target.json meta dict (structural).
    Supports both legacy and v1 schemas.

    Required:
      - id (str)
      - name (str)
      - capabilities (dict)
      - emitter module path key: 'emitter' OR 'emitter_module'
    """
    errors: List[str] = []
    if not isinstance(meta, dict):
        return False, ["target meta is not dict"]

    def _req_str(k: str) -> None:
        v = meta.get(k)
        if not isinstance(v, str) or not v.strip():
            errors.append(f"missing or invalid key: {k}")

    _req_str("id")
    _req_str("name")

    caps = meta.get("capabilities")
    if not isinstance(caps, dict):
        errors.append("missing or invalid key: capabilities (dict required)")

    em = meta.get("emitter") or meta.get("emitter_module")
    if not isinstance(em, str) or not em.strip():
        errors.append("missing emitter (expected 'emitter' or 'emitter_module')")

    # Optional: platformio if present must be dict
    pio = meta.get("platformio")
    if pio is not None and not isinstance(pio, dict):
        errors.append("platformio must be dict if present")

    return (len(errors) == 0), errors
