from __future__ import annotations

import os
import sys
from pathlib import Path

# Keep local runs from dirtying the working tree with bytecode caches.
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

# Some toolchains/plugins may still attempt to emit bytecode caches.
# Redirect any such writes outside the repo so local validation stays clean.
_repo_root = Path(__file__).resolve().parent
_artifact_pycache = (_repo_root.parent / "artifacts" / "pycache")
_artifact_pycache.mkdir(parents=True, exist_ok=True)
try:
    sys.pycache_prefix = str(_artifact_pycache)
except Exception:
    pass
