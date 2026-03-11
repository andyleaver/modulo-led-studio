from __future__ import annotations
from collections import deque
from typing import Deque, List

# --- diagnostics helper (no silent failure) ---
try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None

def _diag_exc(e: Exception, where: str):
    try:
        if _DIAGS is not None:
            _DIAGS.exception(e, domain="PROJECT", code="LOG_BUFFER_EXCEPTION", summary=where)
    except Exception:
        pass
_MAX = 400
_buf: Deque[str] = deque(maxlen=_MAX)

def push(line: str) -> None:
    try:
        _buf.append(str(line))
    except Exception as e:
        _diag_exc(e, "app/log_buffer.py")

def tail(n: int = 200) -> List[str]:
    try:
        if n <= 0:
            return []
        return list(_buf)[-n:]
    except Exception:
        return []
