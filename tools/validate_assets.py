#!/usr/bin/env python3
"""Validate asset modules for export-safety.

This validator is intentionally strict on structure (so assets never break export)
while being light-touch on compression strategy (so teams can iterate).

Rules enforced:
- Every behaviors/assets/*.py (excluding __init__.py) must import cleanly.
- Must expose an `ASSETS` dict.
- Each asset entry must be a dict with keys: w, h, pix.
- pix must be a flat list length w*h.
- pixels must be 3-tuples of ints in 0..255.

Optional (warn-only):
- If unique colors > 256 for any asset, emit a warning (palette targets).
"""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Set, Tuple

RGB = Tuple[int, int, int]


@dataclass
class Issue:
    level: str  # 'ERR' | 'WARN'
    module: str
    message: str


def _iter_asset_modules(repo_root: Path) -> Iterable[Path]:
    assets_dir = repo_root / 'behaviors' / 'assets'
    if not assets_dir.exists():
        return []
    for p in sorted(assets_dir.glob('*.py')):
        if p.name == '__init__.py':
            continue
        if p.name.startswith('_'):
            continue
        yield p


def _unique_colors(pix: List[RGB]) -> int:
    s: Set[RGB] = set()
    for rgb in pix:
        s.add(rgb)
        if len(s) > 257:
            # short circuit
            return len(s)
    return len(s)


def validate_module(modname: str) -> List[Issue]:
    issues: List[Issue] = []
    try:
        mod = importlib.import_module(modname)
    except Exception as e:
        issues.append(Issue('ERR', modname, f'Import failed: {e!r}'))
        return issues

    if not hasattr(mod, 'ASSETS'):
        issues.append(Issue('ERR', modname, 'Missing ASSETS dict'))
        return issues

    assets = getattr(mod, 'ASSETS')
    if not isinstance(assets, dict):
        issues.append(Issue('ERR', modname, f'ASSETS is not a dict (got {type(assets).__name__})'))
        return issues

    for key, entry in assets.items():
        if not isinstance(entry, dict):
            issues.append(Issue('ERR', modname, f"ASSETS['{key}'] is not a dict"))
            continue
        for req in ('w', 'h', 'pix'):
            if req not in entry:
                issues.append(Issue('ERR', modname, f"ASSETS['{key}'] missing '{req}'"))
        if any(req not in entry for req in ('w', 'h', 'pix')):
            continue

        w, h, pix = entry['w'], entry['h'], entry['pix']
        if not (isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0):
            issues.append(Issue('ERR', modname, f"ASSETS['{key}'] invalid w/h: {w!r}/{h!r}"))
            continue
        if not isinstance(pix, (list, tuple)):
            issues.append(Issue('ERR', modname, f"ASSETS['{key}'].pix is not list/tuple"))
            continue
        if len(pix) != w * h:
            issues.append(Issue('ERR', modname, f"ASSETS['{key}'].pix length {len(pix)} != w*h ({w*h})"))
            continue

        # validate pixel tuples
        for i, rgb in enumerate(pix):
            if not (isinstance(rgb, (list, tuple)) and len(rgb) == 3):
                issues.append(Issue('ERR', modname, f"ASSETS['{key}'].pix[{i}] not an RGB triplet"))
                break
            r, g, b = rgb
            if not all(isinstance(v, int) for v in (r, g, b)):
                issues.append(Issue('ERR', modname, f"ASSETS['{key}'].pix[{i}] has non-int channel(s): {rgb!r}"))
                break
            if not all(0 <= v <= 255 for v in (r, g, b)):
                issues.append(Issue('ERR', modname, f"ASSETS['{key}'].pix[{i}] out of range 0..255: {rgb!r}"))
                break

        # warn on palette heaviness
        try:
            uc = _unique_colors(list(pix))
            if uc > 256:
                issues.append(Issue('WARN', modname, f"ASSETS['{key}'] uses {uc} unique colors (palette targets may need packing)"))
        except Exception:
            # ignore palette computation issues
            pass

    return issues


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    # Make repo importable
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    issues: List[Issue] = []

    for p in _iter_asset_modules(repo_root):
        modname = f"behaviors.assets.{p.stem}"
        issues.extend(validate_module(modname))

    errs = [i for i in issues if i.level == 'ERR']
    warns = [i for i in issues if i.level == 'WARN']

    if issues:
        print('== Asset Validation ==')
        for i in issues:
            print(f"[{i.level}] {i.module}: {i.message}")
        print(f"Summary: {len(errs)} ERR, {len(warns)} WARN")
    else:
        print('== Asset Validation ==')
        print('OK: no issues found')

    return 1 if errs else 0


if __name__ == '__main__':
    raise SystemExit(main())
