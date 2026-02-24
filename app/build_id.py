"""Build/packaging identity.

Purpose:
- Provide a single source of truth for the build identifier printed in startup probes,
  health reports, and crash logs.
- Avoid hard-coding build ids across multiple modules (common cause of confusion when
  folders are renamed or users run different packages).

Contract:
- The build id is read from BUILD_ID.txt located at the repository/package root.
- If the file is missing or unreadable, a safe fallback string is returned.

This module must remain dependency-light (no Qt imports) so it can be used anywhere.
"""

from __future__ import annotations

from pathlib import Path


DEFAULT_BUILD_ID = "HUB75_UI_V52_MARIO_RUN_WRAP_TIME_ALIGN"


def get_repo_root(start: Path) -> Path:
    """Walk upwards from *start* looking for BUILD_ID.txt.

    Returns the directory that contains BUILD_ID.txt, or *start* if not found.
    """
    start = Path(start).resolve()
    if start.is_file():
        start = start.parent
    cur = start
    for _ in range(6):  # keep bounded; packages are shallow
        if (cur / "BUILD_ID.txt").is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start


def read_build_id(repo_root: Path) -> str:
    p = Path(repo_root) / "BUILD_ID.txt"
    try:
        txt = p.read_text(encoding="utf-8").strip()
        if txt:
            return txt
    except Exception:
        pass
    return DEFAULT_BUILD_ID


def get_build_id(start: Path) -> str:
    """Return the build id string for the current package."""
    root = get_repo_root(start)
    return read_build_id(root)
