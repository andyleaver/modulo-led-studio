from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any, Set, Tuple

SystemFn = Callable[[Dict[str, Any]], None]

@dataclass
class SystemNode:
    name: str
    fn: SystemFn
    after: Set[str] = field(default_factory=set)
    before: Set[str] = field(default_factory=set)
    enabled: bool = True

class SystemSchedulerV1:
    """A tiny, deterministic system scheduler for engine primitives.

    Purpose:
      - Provide an explicit update ordering for engine subsystems (agents, particles,
        buffers, narrative, etc.) independent from layer 'effects'.
      - Remain UI-agnostic and safe if no systems are registered.

    Usage:
      scheduler.register("particles", tick_particles, after={"time"}, before={"render"})
      scheduler.tick(ctx)
    """

    def __init__(self):
        self._nodes: Dict[str, SystemNode] = {}
        self._order: List[str] = []
        self._dirty: bool = True

    def register(self, name: str, fn: SystemFn, *, after: Optional[Set[str]] = None, before: Optional[Set[str]] = None, enabled: bool = True):
        self._nodes[name] = SystemNode(
            name=name,
            fn=fn,
            after=set(after or set()),
            before=set(before or set()),
            enabled=bool(enabled),
        )
        self._dirty = True

    def enable(self, name: str, enabled: bool = True):
        if name in self._nodes:
            self._nodes[name].enabled = bool(enabled)

    def unregister(self, name: str):
        if name in self._nodes:
            del self._nodes[name]
            self._dirty = True

    def _rebuild_order(self):
        # Build dependency graph with 'after' edges: A after B => B -> A
        nodes = list(self._nodes.values())
        deps: Dict[str, Set[str]] = {n.name: set(n.after) for n in nodes}
        # Apply 'before' by converting to after constraints
        for n in nodes:
            for b in n.before:
                deps.setdefault(b, set())
                deps[n.name].discard(b)  # n before b => b after n
                deps[b].add(n.name)

        # Ensure all referenced nodes exist in deps
        for name, ds in list(deps.items()):
            for d in list(ds):
                if d not in deps:
                    deps[d] = set()

        # Kahn topo sort, deterministic by name
        incoming = {k: set(v) for k, v in deps.items()}
        order: List[str] = []
        ready = sorted([k for k, v in incoming.items() if not v])

        while ready:
            n = ready.pop(0)
            order.append(n)
            for m, v in incoming.items():
                if n in v:
                    v.remove(n)
                    if not v and m not in order and m not in ready:
                        ready.append(m)
            ready.sort()

        # If cycle, fall back to alphabetical but keep stability
        if len(order) != len(incoming):
            order = sorted(incoming.keys())

        # Only keep nodes that are actually registered
        self._order = [n for n in order if n in self._nodes]
        self._dirty = False

    def tick(self, ctx: Dict[str, Any]):
        if self._dirty:
            self._rebuild_order()
        for name in self._order:
            node = self._nodes.get(name)
            if not node or not node.enabled:
                continue
            try:
                node.fn(ctx)
            except Exception:
                # Scheduler must never crash preview; errors are handled by callers/health checks
                try:
                    import traceback
                    ctx.setdefault("_system_errors", []).append({"system": name, "trace": traceback.format_exc()})
                except Exception:
                    pass

    def snapshot(self) -> Dict[str, Any]:
        if self._dirty:
            self._rebuild_order()
        return {
            "systems": [
                {"name": n, "enabled": bool(self._nodes[n].enabled), "after": sorted(self._nodes[n].after), "before": sorted(self._nodes[n].before)}
                for n in self._order
                if n in self._nodes
            ]
        }
