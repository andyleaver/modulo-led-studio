"""Run lightweight preview truth selftests.

Usage:
    python -m preview.run_selftest
"""

from __future__ import annotations

from preview.viewport import Viewport
from preview.selfcheck import check_viewport_roundtrip


def main() -> int:
    vp = Viewport()
    err = check_viewport_roundtrip(vp, samples=10)
    if err:
        print("SELFTEST FAIL:", err)
        return 1
    print("SELFTEST OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
