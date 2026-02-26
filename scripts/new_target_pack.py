#!/usr/bin/env python3
"""Scaffold a new export target pack under user_targets/export_targets/<target_id>.

Usage:
  python3 scripts/new_target_pack.py my_target_id "My Target Name"
"""

from __future__ import annotations
import json, sys
from pathlib import Path

def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: new_target_pack.py <target_id> <target_name>")
        return 2
    tid = sys.argv[1].strip()
    name = sys.argv[2].strip()
    if not tid or any(c in tid for c in " \t/\\"):
        print("Invalid target_id. Use a simple id like: my_board_fastled_noneaudio")
        return 2

    repo_root = Path(__file__).resolve().parents[1]
    out_dir = repo_root / "user_targets" / "export_targets" / tid
    tpl_dir = out_dir / "templates"
    out_dir.mkdir(parents=True, exist_ok=True)
    tpl_dir.mkdir(parents=True, exist_ok=True)

    target_json = {
        "id": tid,
        "name": name,
        "emitter_module": "emitter.py",
        "capabilities": {
            "targets": ["strip", "matrix"],
            "led_backends": ["fastled"],
            "audio_backends": ["none"],
            "defaults": {"led_backend": "fastled", "audio_backend": "none"},
        },
        "hooks": {
            "extra_includes": "",
            "extra_defines": "",
            "prelude_cpp": "",
            "setup_cpp": "",
            "loop_begin_cpp": "",
            "loop_end_cpp": ""
        },
        "platformio": {
            "platform": "",
            "board": "",
            "framework": "arduino",
            "lib_deps": ["fastled/FastLED@^3.6.0"],
        },
    }
    (out_dir / "target.json").write_text(json.dumps(target_json, indent=2) + "\n", encoding="utf-8")

    emitter_py = """from __future__ import annotations

from typing import Dict, Any
from pathlib import Path

def emit(project: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    \"\"\"Minimal emitter scaffold.

    Must return dict with:
      - files: { "sketch.ino": "<text>", ... }
      - meta:  { ... }
    \"\"\"
    root = Path(__file__).resolve().parent
    tpl = (root / "templates" / "sketch_fastled.ino.tpl").read_text(encoding="utf-8")
    sketch = tpl.replace("{BUILD_ID}", str(ctx.get("build_id","")))
    return {"files": {"sketch.ino": sketch}, "meta": {"target_id": ctx.get("target_id")}}
"""
    (out_dir / "emitter.py").write_text(emitter_py, encoding="utf-8")

    sketch_tpl = """// {BUILD_ID}
// Minimal scaffold sketch. Replace with real exporter output.
#include <Arduino.h>
void setup() { }
void loop() { }
"""
    (tpl_dir / "sketch_fastled.ino.tpl").write_text(sketch_tpl + "\n", encoding="utf-8")

    print(f"Created target pack at: {out_dir}")
    print("Next: edit target.json capabilities and implement emitter.emit().")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
