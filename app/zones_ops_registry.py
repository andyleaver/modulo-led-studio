from __future__ import annotations

"""Zones/Masks Operations Registry

Canonical backend for composing index sets used by mask resolution and targeting.

This file was previously scaffold-only; it is now wired and import-safe.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Union

IndexSet = Set[int]
MaskLike = Union[Dict[str, Any], List[int], Set[int], tuple]


@dataclass(frozen=True)
class ZoneOp:
    key: str
    label: str
    fn: Callable[[IndexSet, IndexSet], IndexSet]


_OPS: Dict[str, ZoneOp] = {}


def register_zone_op(op: ZoneOp) -> None:
    k = (op.key or "").strip().lower()
    if not k:
        raise ValueError("ZoneOp.key required")
    if k in _OPS:
        raise ValueError(f"Duplicate zone op: {k}")
    _OPS[k] = ZoneOp(key=k, label=op.label or k, fn=op.fn)


def get_zone_op(key: str) -> Optional[ZoneOp]:
    return _OPS.get((key or "").strip().lower())


def list_zone_ops() -> List[ZoneOp]:
    return [_OPS[k] for k in sorted(_OPS.keys())]


def normalize_to_index_set(mask_like: Any, *, n: Optional[int] = None) -> IndexSet:
    """Normalize various mask-like forms into an index set.
    Supports:
      - {"indices":[...]}
      - {"start": int, "end": int} inclusive
      - list/tuple/set of ints
    """
    out: IndexSet = set()
    if mask_like is None:
        return out

    if isinstance(mask_like, dict):
        if "indices" in mask_like:
            try:
                for v in (mask_like.get("indices") or []):
                    out.add(int(v))
            except Exception:
                return set()
            return _clamp_set(out, n)
        if "start" in mask_like and "end" in mask_like:
            try:
                a = int(mask_like.get("start"))
                b = int(mask_like.get("end"))
            except Exception:
                return set()
            if a > b:
                a, b = b, a
            out = set(range(a, b + 1))
            return _clamp_set(out, n)
        return set()

    if isinstance(mask_like, (list, tuple, set)):
        try:
            for v in mask_like:
                out.add(int(v))
        except Exception:
            return set()
        return _clamp_set(out, n)

    return set()


def _clamp_set(s: IndexSet, n: Optional[int]) -> IndexSet:
    if n is None:
        return set(i for i in s if i >= 0)
    return set(i for i in s if 0 <= i < int(n))


# Built-in boolean ops
def _op_union(a: IndexSet, b: IndexSet) -> IndexSet:
    return set(a) | set(b)

def _op_intersect(a: IndexSet, b: IndexSet) -> IndexSet:
    return set(a) & set(b)

def _op_subtract(a: IndexSet, b: IndexSet) -> IndexSet:
    return set(a) - set(b)

def _op_xor(a: IndexSet, b: IndexSet) -> IndexSet:
    return set(a) ^ set(b)

try:
    register_zone_op(ZoneOp("union", "Union", _op_union))
    register_zone_op(ZoneOp("intersect", "Intersect", _op_intersect))
    register_zone_op(ZoneOp("subtract", "Subtract", _op_subtract))
    register_zone_op(ZoneOp("xor", "XOR", _op_xor))
except Exception:
    pass
