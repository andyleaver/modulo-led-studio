"""Extension Points (v1)

Modulo is LED-first. This module provides *engine-only* extension hooks so
community features can plug in without patching core files.

Goals:
- Safe: extension failures must not crash the app.
- Deterministic: stable ordering of hooks.
- Minimal: no hardware assumptions, no UI requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---- Signal Providers -------------------------------------------------------

# A signal provider is called once per frame and may return a dict of signal key->value
SignalProvider = Callable[[Dict[str, Any]], Dict[str, Any]]

_SIGNAL_PROVIDERS: List[Tuple[str, SignalProvider]] = []


def register_signal_provider(name: str, fn: SignalProvider) -> None:
    """Register a derived-signal provider.

    The provider receives a context dict (engine-dependent) and returns a dict of
    additional signals. Providers should only write keys they own (prefixed).
    """
    if not isinstance(name, str) or not name.strip():
        return
    if not callable(fn):
        return
    _SIGNAL_PROVIDERS.append((name.strip(), fn))
    _SIGNAL_PROVIDERS.sort(key=lambda x: x[0])


def collect_signal_overrides(ctx: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, fn in list(_SIGNAL_PROVIDERS):
        try:
            d = fn(ctx or {})
            if isinstance(d, dict):
                out.update(d)
        except Exception:
            # Never let plugins break the engine
            continue
    return out


# ---- Rule Actions -----------------------------------------------------------

RuleActionFn = Callable[[Dict[str, Any]], Dict[str, Any]]

_RULE_ACTIONS: Dict[str, RuleActionFn] = {}


def register_rule_action(kind: str, fn: RuleActionFn) -> None:
    """Register a custom Rules V6 action.

    The action receives a context dict containing:
      project, signals, variables, prev_state, action, rule_id

    It returns a dict:
      variables: {number/toggle updates}
      project_mutations: {...}  (optional)
      errors: [str] (optional)
    """
    if not isinstance(kind, str) or not kind.strip():
        return
    if not callable(fn):
        return
    _RULE_ACTIONS[kind.strip()] = fn


def get_rule_action(kind: str) -> Optional[RuleActionFn]:
    return _RULE_ACTIONS.get(str(kind or "").strip())



# ---- Engine Systems ---------------------------------------------------------

SystemTickFn = Callable[[Dict[str, Any]], None]
_SYSTEMS: List[Tuple[str, SystemTickFn, Set[str], Set[str], bool]] = []

def register_system(name: str, fn: SystemTickFn, *, after: Optional[Set[str]] = None, before: Optional[Set[str]] = None, enabled: bool = True) -> None:
    """Register an engine system to be scheduled each frame.

    Systems are UI-agnostic. They receive the same ctx dict used by the scheduler.
    """
    if not isinstance(name, str) or not name.strip():
        return
    if not callable(fn):
        return
    _SYSTEMS.append((name.strip(), fn, set(after or set()), set(before or set()), bool(enabled)))
    _SYSTEMS.sort(key=lambda x: x[0])

def collect_system_registrations() -> List[Tuple[str, SystemTickFn, Set[str], Set[str], bool]]:
    return list(_SYSTEMS)


# ---- Health Probes ----------------------------------------------------------

HealthProbe = Callable[[], Dict[str, Any]]
_HEALTH_PROBES: List[Tuple[str, HealthProbe]] = []


def register_health_probe(name: str, fn: HealthProbe) -> None:
    if not isinstance(name, str) or not name.strip():
        return
    if not callable(fn):
        return
    _HEALTH_PROBES.append((name.strip(), fn))
    _HEALTH_PROBES.sort(key=lambda x: x[0])


def collect_health_probe_data() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, fn in list(_HEALTH_PROBES):
        try:
            d = fn()
            if isinstance(d, dict):
                out[name] = d
        except Exception:
            continue
    return out

# ---- Built-in engine primitives that register via extensions ----------------
# Importing these is safe; they only register hooks and do not add UI/peripherals.
try:
    import runtime.spawner_v1  # noqa: F401
except Exception:
    pass

# Perf probe (preview-side) — safe even in headless export runs.
try:
    import preview.performance_health  # noqa: F401
except Exception:
    pass
