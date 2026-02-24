"""Backward-compatible re-exports for purpose channel keys.

Canonical: `params.purpose_contract`.
"""

from __future__ import annotations

from params.purpose_contract import FLOAT_KEYS, INT_KEYS, SPECS, PurposeSpec, ensure, clamp

__all__ = [
    "FLOAT_KEYS",
    "INT_KEYS",
    "SPECS",
    "PurposeSpec",
    "ensure",
    "clamp",
]
