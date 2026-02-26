#!/usr/bin/env python3
"""
Validate Modulo export target packs (export/targets/**/target.json).

This is meant to fail fast in CI when a new target pack is missing required fields
(e.g. id/emitter_module/capabilities) or has schema drift.

Usage:
  python3 tools/validate_target_packs.py
  python3 tools/validate_target_packs.py --targets-dir export/targets
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

REQUIRED_TOP_LEVEL = [
    "id",
    "name",
    "arch",
    "emitter_module",
    "capabilities",
    "toolchain",
]
REQUIRED_CAPABILITIES = [
    "defaults",
    "led_backends",
    "supports_matrix",
    "supports_postfx_runtime",
    "supports_operators_runtime",
]

@dataclass
class Issue:
    path: str
    msg: str

def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def validate_one(target_json_path: str) -> List[Issue]:
    issues: List[Issue] = []
    try:
        obj = load_json(target_json_path)
    except Exception as e:
        return [Issue(target_json_path, f"invalid json: {e}")]

    # required keys
    for k in REQUIRED_TOP_LEVEL:
        if k not in obj:
            issues.append(Issue(target_json_path, f"missing required key: {k}"))

    # basic value checks
    tid = obj.get("id")
    if not isinstance(tid, str) or not tid.strip():
        issues.append(Issue(target_json_path, "id must be a non-empty string"))

    emitter = obj.get("emitter_module")
    if not isinstance(emitter, str) or not emitter.strip():
        issues.append(Issue(target_json_path, "emitter_module must be a non-empty string"))

    caps = obj.get("capabilities")
    if not isinstance(caps, dict):
        issues.append(Issue(target_json_path, "capabilities must be an object"))
        caps = {}

    for k in REQUIRED_CAPABILITIES:
        if k not in caps:
            issues.append(Issue(target_json_path, f"capabilities missing key: {k}"))

    # defaults must exist and be dict
    defaults = caps.get("defaults")
    if defaults is not None and not isinstance(defaults, dict):
        issues.append(Issue(target_json_path, "capabilities.defaults must be an object"))

    # sanity: folder name should match id
    folder = os.path.basename(os.path.dirname(target_json_path))
    if isinstance(tid, str) and tid.strip() and folder != tid:
        issues.append(Issue(target_json_path, f"folder name '{folder}' does not match id '{tid}'"))

    return issues

def find_target_jsons(targets_dir: str) -> List[str]:
    out: List[str] = []
    for root, _, files in os.walk(targets_dir):
        for fn in files:
            if fn == "target.json":
                out.append(os.path.join(root, fn))
    return sorted(out)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets-dir", default=os.path.join("export", "targets"))
    args = ap.parse_args()

    targets_dir = args.targets_dir
    if not os.path.isdir(targets_dir):
        print(f"ERR: targets dir not found: {targets_dir}", file=sys.stderr)
        return 2

    target_jsons = find_target_jsons(targets_dir)
    if not target_jsons:
        print(f"ERR: no target.json files found under: {targets_dir}", file=sys.stderr)
        return 2

    all_issues: List[Issue] = []
    for path in target_jsons:
        all_issues.extend(validate_one(path))

    if all_issues:
        print("Target pack validation FAILED:")
        for iss in all_issues:
            print(f"- {iss.path}: {iss.msg}")
        print(f"\nTotal issues: {len(all_issues)}")
        return 1

    print(f"OK: validated {len(target_jsons)} target packs.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
