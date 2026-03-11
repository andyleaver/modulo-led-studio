"""Canonical behavior template.

1) Copy this file to ``behaviors/effects/<your_behavior_key>.py``.
2) Rename ``BEHAVIOR_ID`` and ``BEHAVIOR_TITLE``.
3) Fill in ``preview_emit(...)`` for preview/runtime use.
4) Fill in ``arduino_emit(...)`` only when the behavior is exportable.
5) Add a capabilities entry before registering it.
"""

from __future__ import annotations

from typing import Any, Dict

from behaviors.registry import BehaviorDef

BEHAVIOR_ID = "<your_behavior_key>"
BEHAVIOR_TITLE = "<Human Title>"


def preview_emit(*, params: Dict[str, Any] | None = None, **kwargs: Any) -> Dict[str, Any]:
    """Return preview/runtime metadata for the behavior.

    Accepts the current PreviewEngine-style kwargs superset so new optional context
    values do not immediately invalidate the template contract.
    """
    return {
        "behavior": BEHAVIOR_ID,
        "title": BEHAVIOR_TITLE,
        "params": dict(params or {}),
        "meta": {"template": True},
    }


def arduino_emit(*, params: Dict[str, Any] | None = None, **kwargs: Any) -> Dict[str, Any]:
    """Return exporter metadata for the behavior."""
    return {
        "behavior": BEHAVIOR_ID,
        "title": BEHAVIOR_TITLE,
        "params": dict(params or {}),
        "meta": {"template": True, "export": True},
    }


def build_behavior_def() -> BehaviorDef:
    """Construct the canonical behavior definition for this template.

    Registration is intentionally left to the copied behavior file, after the key and
    capabilities entry have been made real.
    """
    return BehaviorDef(
        BEHAVIOR_ID,
        title=BEHAVIOR_TITLE,
        preview_emit=preview_emit,
        arduino_emit=arduino_emit,
    )
