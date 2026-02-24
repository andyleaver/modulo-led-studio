"""Codemap must be fully resolvable (no ∅).

This is a contributor guardrail: when symbols move, update app/codemap.py.
"""

from __future__ import annotations


def main() -> None:
    from app.codemap import build_codemap

    cm = build_codemap()
    missing = [k for k, v in cm.items() if v is None]
    if missing:
        raise AssertionError("codemap unresolved entries: " + ", ".join(sorted(missing)))


if __name__ == "__main__":
    main()
