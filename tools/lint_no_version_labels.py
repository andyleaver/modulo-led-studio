"""
Lint: forbid version labels inside code (Release R10 helper).

Policy:
- No "FIX###", "STAGE###", "BUILD###" tokens inside source code text.
- Versions belong in git tags/releases/changelog, not in runtime code.

This tool scans .py/.md/.txt/.json files under the repo root and reports violations.
It does not auto-fix; it is a guardrail to run near the end of the release process.

Usage:
  python3 tools/lint_no_version_labels.py
"""

from __future__ import annotations
from pathlib import Path
import re
import sys

PATTERNS = [
    re.compile(r"\bFIX\d+\b", re.IGNORECASE),
    re.compile(r"\bSTAGE\d+\b", re.IGNORECASE),
    re.compile(r"\bBUILD\d+\b", re.IGNORECASE),
    re.compile(r"\bREFAC\d+\b", re.IGNORECASE),
]

EXTS = {".py", ".md", ".txt", ".json"}

def main() -> int:
    root = Path(__file__).resolve().parents[1]
    bad = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in EXTS:
            continue
        # Avoid scanning large binary-ish outputs
        if "out" in p.parts and p.suffix.lower() in {".json", ".txt"}:
            continue
        try:
            s = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for pat in PATTERNS:
            m = pat.search(s)
            if m:
                # record first occurrence line
                i = m.start()
                line = s.count("\n", 0, i) + 1
                bad.append((str(p.relative_to(root)), line, m.group(0)))
                break

    if bad:
        print("== Version label violations ==")
        for fp, line, tok in bad[:200]:
            print(f"{fp}:{line}: {tok}")
        if len(bad) > 200:
            print(f"... and {len(bad)-200} more")
        return 2
    print("OK: no version labels found.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
