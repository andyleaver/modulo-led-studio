from __future__ import annotations

"""Public Mod API (v1)

This wraps existing, stable extension points.
"""

from typing import Any, Callable, Dict, Optional


def register_effect(
    key: str,
    *,
    preview_emit: Callable[..., Any],
    arduino_emit: Optional[Callable[..., Any]] = None,
    capabilities: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None,
) -> None:
    """Register an effect.

    Notes:
    - Core registry expects a BehaviorDef and requires capabilities.
    - Mods may provide capabilities inline (no need to edit capabilities_catalog.json).
    - Mods must provide arduino_emit (Modulo policy: if it previews, it exports).
    """
    from behaviors.registry import BehaviorDef, register

    caps = dict(capabilities or {})
    caps.setdefault("shipped", False)
    # A tiny compatibility hint used by docs / capability map.
    caps.setdefault("origin", "mod")
    if arduino_emit is None:
        raise ValueError("Mods must provide arduino_emit (Modulo policy: if it previews, it exports).")
    caps.setdefault("export", "exportable")

    defn = BehaviorDef(
        key,
        preview_emit=preview_emit,
        arduino_emit=arduino_emit,
        title=title or key,
        capabilities=caps,
    )
    register(defn)


def register_rule_action(kind: str, fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
    from runtime.extensions_v1 import register_rule_action as _reg
    _reg(kind, fn)


def register_signal_provider(name: str, fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
    from runtime.extensions_v1 import register_signal_provider as _reg
    _reg(name, fn)


def register_system(name: str, fn: Callable[[Dict[str, Any]], None], *, after=None, before=None, enabled: bool = True) -> None:
    from runtime.extensions_v1 import register_system as _reg
    _reg(name, fn, after=after, before=before, enabled=enabled)


def register_ca_module(
    *,
    name: str,
    kind: str,
    description: str,
    py_step,
    cpp_step_body: str,
) -> None:
    """Register a custom CA module.

    This is an advanced escape hatch: cpp_step_body is embedded into Arduino export.
    """
    from runtime.ca_modules_v1 import CAModuleV1, register_ca_module as _reg
    _reg(CAModuleV1(name=name, kind=kind, description=description, py_step=py_step, cpp_step_body=cpp_step_body))
