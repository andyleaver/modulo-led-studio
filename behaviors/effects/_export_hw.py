from __future__ import annotations


def resolve_data_pin(surface: dict | None, default: int = 6) -> int:
    """Return canonical strip data pin for behavior-local Arduino emitters.

    Canonical callers should provide ``surface["data_pin"]`` when invoking
    effect-local export emitters. The legacy ``led_pin`` mirror is accepted only
    as a compatibility alias at this helper boundary so shipped behavior modules
    do not each carry their own shadow-key reads.
    """
    lay = surface or {}
    raw = None
    try:
        raw = lay.get("data_pin")
    except Exception:
        raw = None
    if raw in (None, ""):
        try:
            raw = lay.get("led_pin")
        except Exception:
            raw = None
    if raw in (None, ""):
        raw = default
    try:
        return int(raw)
    except Exception:
        try:
            return int(str(raw).strip() or default)
        except Exception:
            return int(default)
