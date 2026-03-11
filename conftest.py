from __future__ import annotations

import os
import sys
from pathlib import Path

# Keep the working tree clean during local/selftest runs.
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

# Pytest/plugin import order can still leave bytecode behind. Redirect any
# residual cache writes outside the repo tree.
_repo_root = Path(__file__).resolve().parent
_artifact_pycache = (_repo_root.parent / "artifacts" / "pycache")
_artifact_pycache.mkdir(parents=True, exist_ok=True)
try:
    sys.pycache_prefix = str(_artifact_pycache)
except Exception:
    pass



def _cleanup_repo_bytecode() -> None:
    for path in (_repo_root / "__pycache__",):
        if path.exists():
            import shutil
            shutil.rmtree(path, ignore_errors=True)
    for pattern in ("*.pyc", "*.pyo"):
        for path in _repo_root.rglob(pattern):
            try:
                path.unlink()
            except OSError:
                pass


_cleanup_repo_bytecode()


def pytest_sessionfinish(session, exitstatus):
    _cleanup_repo_bytecode()
