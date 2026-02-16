from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Any, Tuple

from ..ir import ShowIR

EmitFn = Callable[[ShowIR, Path], Tuple[Path, str]]

@dataclass(frozen=True)
class TargetSpec:
    id: str
    name: str
    meta: Dict[str, Any]
    emit: Callable[..., Tuple[Path, str]]
