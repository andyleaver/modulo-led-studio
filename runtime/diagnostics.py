from __future__ import annotations

"""
runtime.diagnostics

Minimal diagnostics ring-buffer for "no silent failure" policy.

This is intentionally lightweight:
- preview/runtime can record exceptions without importing Qt
- UI can poll/app_core can forward events into the Diagnostics Console

If a richer system already exists, this module can be used as a shim.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List, Literal
import time
import traceback
import uuid

DiagLevel = Literal["DEBUG","INFO","WARN","ERROR","FATAL"]
DiagDomain = Literal["STARTUP","UI","PROJECT","PREVIEW","RUNTIME","EXPORT","KERNEL","RULES","MAPPING","COMPOSITION"]
DiagKind = Literal["MESSAGE","EXCEPTION","BUDGET","PROBE","GATE"]

@dataclass
class DiagnosticsEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    t_unix: float = field(default_factory=lambda: time.time())
    frame: Optional[int] = None

    level: DiagLevel = "INFO"
    domain: DiagDomain = "RUNTIME"
    kind: DiagKind = "MESSAGE"
    code: str = ""
    summary: str = ""

    app_id: Optional[str] = None
    project_id: Optional[str] = None
    layer_id: Optional[str] = None
    layer_name: Optional[str] = None
    behavior_id: Optional[str] = None
    target_id: Optional[str] = None

    details: Dict[str, Any] = field(default_factory=dict)

    exc_type: Optional[str] = None
    exc_msg: Optional[str] = None
    exc_stack: Optional[str] = None

    probe_id: Optional[str] = None
    pass_fail: Optional[bool] = None
    evidence: Optional[Dict[str, Any]] = None

    correlation_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)

class DiagnosticsBuffer:
    def __init__(self, capacity: int = 200):
        self.capacity = int(capacity)
        self._buf: List[DiagnosticsEvent] = []
        self._dropped = 0

    def record(self, ev: DiagnosticsEvent) -> None:
        if len(self._buf) >= self.capacity:
            self._buf.pop(0)
            self._dropped += 1
        self._buf.append(ev)

    def message(self, *, level: DiagLevel="INFO", domain: DiagDomain="RUNTIME", code: str="", summary: str="",
                frame: Optional[int]=None, layer_id: Optional[str]=None, layer_name: Optional[str]=None,
                behavior_id: Optional[str]=None, target_id: Optional[str]=None, project_id: Optional[str]=None,
                app_id: Optional[str]=None, correlation_id: Optional[str]=None, details: Optional[Dict[str,Any]]=None) -> None:
        self.record(DiagnosticsEvent(
            level=level, domain=domain, kind="MESSAGE", code=code, summary=summary,
            frame=frame, layer_id=layer_id, layer_name=layer_name, behavior_id=behavior_id,
            target_id=target_id, project_id=project_id, app_id=app_id, correlation_id=correlation_id,
            details=details or {},
        ))

    def exception(self, e: BaseException, *, level: DiagLevel="ERROR", domain: DiagDomain="RUNTIME", code: str="",
                  summary: str="", frame: Optional[int]=None, layer_id: Optional[str]=None, layer_name: Optional[str]=None,
                  behavior_id: Optional[str]=None, target_id: Optional[str]=None, project_id: Optional[str]=None,
                  app_id: Optional[str]=None, correlation_id: Optional[str]=None, details: Optional[Dict[str,Any]]=None) -> None:
        self.record(DiagnosticsEvent(
            level=level, domain=domain, kind="EXCEPTION", code=code, summary=summary or (str(e) or type(e).__name__),
            frame=frame, layer_id=layer_id, layer_name=layer_name, behavior_id=behavior_id,
            target_id=target_id, project_id=project_id, app_id=app_id, correlation_id=correlation_id,
            details=details or {},
            exc_type=type(e).__name__, exc_msg=str(e),
            exc_stack="".join(traceback.format_exception(type(e), e, e.__traceback__))[:5000],
        ))

    def tail(self, n: int = 20) -> List[DiagnosticsEvent]:
        n = max(0, int(n))
        return list(self._buf[-n:])

    @property
    def dropped(self) -> int:
        return int(self._dropped)

# global singleton (opt-in)
GLOBAL_DIAGS = DiagnosticsBuffer()
