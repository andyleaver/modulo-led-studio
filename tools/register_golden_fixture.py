#!/usr/bin/env python3
"""Register a new golden fixture for regression protection.

What it does:
- Optionally creates a fixture JSON under fixtures/projects/ from a small template.
- Adds the fixture filename to tools/golden_exports.py FIXTURES list (idempotent).
- Optionally runs golden_exports.py --update to refresh baseline.

Usage:
  python3 tools/register_golden_fixture.py --name demo_my_new_effect_golden.json --create
  python3 tools/register_golden_fixture.py --name demo_my_new_effect_golden.json
  python3 tools/register_golden_fixture.py --name demo_my_new_effect_golden.json --update-baseline
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.project_model import build_surface_dict

TEMPLATE = {
  "name": "Golden Fixture (edit me)",
  "surface": build_surface_dict(
    kind="cells",
    width=16,
    height=16,
    count=256,
    mapping={"origin": "top_left", "serpentine": True},
  ),
  "layers": [
    {"behavior": "aurora", "enabled": True, "params": {"purpose_f0": 0.0}}
  ]
}


def _add_fixture_to_golden_exports(py_path: Path, fixture_name: str) -> bool:
    txt = py_path.read_text(encoding="utf-8")
    m = re.search(r"FIXTURES\s*=\s*\[(?P<body>.*?)\]\n", txt, re.S)
    if not m:
        raise SystemExit(f"Could not find FIXTURES list in {py_path}")
    body = m.group("body")
    if re.search(rf"\b{re.escape(fixture_name)}\b", body):
        return False

    insertion = f'    "{fixture_name}",\n'
    new_body = body + insertion
    new_txt = txt[:m.start("body")] + new_body + txt[m.end("body"):]
    py_path.write_text(new_txt, encoding="utf-8")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="Fixture filename (e.g. demo_my_effect_golden.json)")
    ap.add_argument("--create", action="store_true", help="Create fixtures/projects/<name> if missing using a safe template")
    ap.add_argument("--update-baseline", action="store_true", help="Run golden_exports.py --update after registering")
    args = ap.parse_args()

    repo_root = REPO_ROOT
    fixture_dir = repo_root / "fixtures" / "projects"
    fixture_dir.mkdir(parents=True, exist_ok=True)

    fixture_path = fixture_dir / args.name
    if args.create and not fixture_path.exists():
        data = dict(TEMPLATE)
        data["name"] = args.name.replace(".json", "")
        fixture_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"Created {fixture_path}")

    golden_exports_py = repo_root / "tools" / "golden_exports.py"
    changed = _add_fixture_to_golden_exports(golden_exports_py, args.name)
    print(("Added" if changed else "Already present"), f"in {golden_exports_py.name}: {args.name}")

    if args.update_baseline:
        cmd = ["python3", str(repo_root / "tools" / "golden_exports.py"), "--update"]
        print("Running:", " ".join(cmd))
        subprocess.check_call(cmd, cwd=str(repo_root))


if __name__ == "__main__":
    main()
