from __future__ import annotations

"""Signal key validation utilities.

Wired implementation: uses the canonical SignalRegistry contract.
"""

from dataclasses import dataclass
from typing import Iterable, List, Optional

from app.signal_registry import REGISTRY, SignalRegistry


@dataclass(frozen=True)
class SignalValidationResult:
    ok: bool
    unknown_keys: List[str]
    message: str


def validate_signal_keys(keys: Iterable[str], registry: Optional[SignalRegistry] = None) -> SignalValidationResult:
    r = registry or REGISTRY
    unknown = r.validate_keys(list(keys))
    if unknown:
        msg = "Unknown signal keys: " + ", ".join(unknown)
        return SignalValidationResult(ok=False, unknown_keys=unknown, message=msg)
    return SignalValidationResult(ok=True, unknown_keys=[], message="OK")
