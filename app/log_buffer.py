from __future__ import annotations
from collections import deque
from typing import Deque, List

_MAX = 400
_buf: Deque[str] = deque(maxlen=_MAX)

def push(line: str) -> None:
    try:
        _buf.append(str(line))
    except Exception:
        pass

def tail(n: int = 200) -> List[str]:
    try:
        if n <= 0:
            return []
        return list(_buf)[-n:]
    except Exception:
        return []
