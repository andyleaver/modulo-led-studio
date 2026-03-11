from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, Literal

KernelState = Literal["IDLE","OK","COMPILE_FAILED","RUNTIME_ERROR","BUDGET_EXCEEDED","DISABLED"]

@dataclass
class KernelStatus:
    state: KernelState = "IDLE"
    source_hash: Optional[str] = None
    api_version: str = "kernel_ctx"

    compile_count: int = 0
    last_compile_ok: bool = False
    last_compile_error: Optional[str] = None

    error_count: int = 0
    last_error: Optional[str] = None
    last_error_frame: Optional[int] = None

    budget_ms: float = 10.0
    strike_limit: int = 3
    strikes: int = 0
    last_budget_event: Optional[str] = None

    disabled_reason: Optional[str] = None

    counters: Dict[str, Any] = None
