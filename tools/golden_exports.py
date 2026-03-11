#!/usr/bin/env python3
"""Golden exports: generate deterministic Arduino sketches for a small fixture set
and compare against stored hashes.

Why:
- Parity sweep tells you *what should export*.
- Compile sanity tells you *it compiles*.
- Golden exports tell you *the emitted code didn't silently change*.

Usage:
  python3 tools/golden_exports.py           # compare against baseline
  python3 tools/golden_exports.py --update  # regenerate baseline (intentional changes)

Notes:
- This uses the Arduino exporter (export/arduino_exporter.py) which writes a single
  .ino sketch per project.
- Baseline lives at golden_exports/golden_exports.json
- Fixtures live at fixtures/projects/*.json
- Mismatch reports default to ../artifacts/parity_reports/golden_mismatch
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.surface_compat import get_surface_kind_value, get_surface_mapping_values, get_default_surface_dict
from export.arduino_exporter import export_project_validated

BASELINE_PATH = REPO_ROOT / "golden_exports" / "golden_exports.json"
PROJECT_FIXTURE_DIR = REPO_ROOT / "fixtures" / "projects"

# A small but representative fixture set shipped with the repo.
FIXTURES = [
    "order_pipeline_lock.json",
    "order_pipeline_lock_matrix8x8.json",
    "order_pipeline_lock_matrix8x8_mapstress.json",
    "order_pipeline_lock_matrix8x8_mapstress2.json",
]

def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _read_text_lines(p: Path) -> List[str]:
    # Arduino exporter output is UTF-8 in our toolchain, but be resilient.
    return p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

def _excerpt(lines: List[str], head: int = 80, tail: int = 40) -> Dict[str, Any]:
    return {
        "line_count": len(lines),
        "head": "".join(lines[:head]),
        "tail": "".join(lines[-tail:]) if len(lines) > tail else "".join(lines),
    }

def _load_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))

def _normalize_project_for_export(project: Dict[str, Any]) -> Dict[str, Any]:
    # Ensure export.hw.matrix exists when canonical surface is cells.
    proj = json.loads(json.dumps(project))  # deep copy
    surface = proj.get("surface")
    if not isinstance(surface, dict):
        surface = get_default_surface_dict()

    kind = get_surface_kind_value(surface, default="strip")

    if kind == "cells":
        w = int(surface.get("width") or 0)
        h = int(surface.get("height") or 0)
        if w > 0 and h > 0:
            mapping = get_surface_mapping_values(surface)
            exp = proj.setdefault("export", {})
            hw = exp.setdefault("hw", {})
            hw.setdefault("matrix", {
                "width": w,
                "height": h,
                "serpentine": mapping["serpentine"],
                "origin": mapping["origin"],
                "rotate": mapping["rotate"],
                "flip_x": mapping["flip_x"],
                "flip_y": mapping["flip_y"],
            })
    return proj

def _export_one(project_path: Path, out_dir: Path) -> Path:
    project = _normalize_project_for_export(_load_json(project_path))
    out_dir.mkdir(parents=True, exist_ok=True)
    written = export_project_validated(project, out_dir / "export.ino")
    return Path(written)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="Regenerate baseline hashes")
    ap.add_argument("--fixtures", nargs="*", default=None, help="Override fixture list")
    ap.add_argument("--out-dir", default=None, help="Directory to write mismatch artifacts (default: ../artifacts/parity_reports/golden_mismatch or $MODULO_ARTIFACT_DIR)")
    args = ap.parse_args()

    fixtures = args.fixtures if args.fixtures else FIXTURES

    missing: List[str] = []
    for fx in fixtures:
        if not (PROJECT_FIXTURE_DIR / fx).exists():
            missing.append(fx)
    if missing:
        print("ERROR: missing demo fixtures:")
        for m in missing:
            print(f"- {m}")
        return 2

    tmp_root = Path(tempfile.mkdtemp(prefix="modulo_golden_"))
    try:
        results: Dict[str, Dict[str, Any]] = {}
        for fx in fixtures:
            proj_path = PROJECT_FIXTURE_DIR / fx
            out_dir = tmp_root / fx.replace(".json", "")
            ino_path = _export_one(proj_path, out_dir)
            ino_lines = _read_text_lines(ino_path)
            results[fx] = {
                "ino_relpath": str(ino_path.relative_to(out_dir)),
                "ino_sha256": _sha256_file(ino_path),
                "ino_bytes": ino_path.stat().st_size,
                "ino_excerpt": _excerpt(ino_lines),
            }
            print(f"OK export: {fx} -> {ino_path.name} ({results[fx]['ino_bytes']} bytes)")

        if args.update or not BASELINE_PATH.exists():
            BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
            BASELINE_PATH.write_text(json.dumps({"fixtures": results}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"Wrote baseline: {BASELINE_PATH}")
            return 0

        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        base_fx = (baseline.get("fixtures") or {})

        mismatches = []
        for fx, cur in results.items():
            prev = base_fx.get(fx)
            if not prev:
                mismatches.append((fx, "missing_in_baseline", cur["ino_sha256"], ""))
                continue
            if str(prev.get("ino_sha256")) != str(cur.get("ino_sha256")):
                mismatches.append((fx, "sha256", cur["ino_sha256"], prev.get("ino_sha256")))

        if mismatches:
            print("\nGOLDEN EXPORT MISMATCHES:")
            base_dir = Path(os.environ.get("MODULO_ARTIFACT_DIR")) if os.environ.get("MODULO_ARTIFACT_DIR") else (REPO_ROOT.parent / "artifacts")
            if args.out_dir:
                mismatch_dir = Path(args.out_dir) / "golden_mismatch"
            else:
                mismatch_dir = base_dir / "parity_reports" / "golden_mismatch"
            mismatch_dir.mkdir(parents=True, exist_ok=True)
            for fx, kind, cur_hash, prev_hash in mismatches:
                print(f"- {fx}: {kind}\n    current: {cur_hash}\n    baseline: {prev_hash}")

                # Write a small diff hint (excerpt-based) so you can spot what changed quickly.
                cur_excerpt = (results.get(fx) or {}).get("ino_excerpt") or {}
                prev_excerpt = (base_fx.get(fx) or {}).get("ino_excerpt") or {}

                cur_blob = (str(cur_excerpt.get("head") or "") + "\n...\n" + str(cur_excerpt.get("tail") or ""))
                prev_blob = (str(prev_excerpt.get("head") or "") + "\n...\n" + str(prev_excerpt.get("tail") or ""))

                diff_txt = "".join(difflib.unified_diff(
                    prev_blob.splitlines(keepends=True),
                    cur_blob.splitlines(keepends=True),
                    fromfile="baseline_excerpt",
                    tofile="current_excerpt",
                ))

                diff_path = mismatch_dir / (fx.replace(".json", "") + ".diff.txt")
                diff_path.write_text(diff_txt, encoding="utf-8")
                print(f"    diff_hint: {diff_path}")

            print("\nIf changes are intentional, run: python3 tools/golden_exports.py --update")
            return 1

        print(f"\nGolden exports OK ({len(results)} fixtures).")
        return 0

    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

if __name__ == "__main__":
    raise SystemExit(main())
