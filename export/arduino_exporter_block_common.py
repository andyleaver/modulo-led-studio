from __future__ import annotations

import re

TOKEN_RE = re.compile(r"@@[A-Z0-9_]+@@")
EXPORT_MARKER = "MODULO_EXPORT"

__all__ = ["TOKEN_RE", "EXPORT_MARKER"]
