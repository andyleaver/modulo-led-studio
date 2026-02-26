#!/usr/bin/env python3
"""Compile sanity (Phase 5B)

Best-effort export + optional compilation checks.

- Always generates representative exports for a few target families.
- If PlatformIO is installed (pio), compiles generated PlatformIO projects.
- If arduino-cli is installed, compiles emitted .ino sketches when an FQBN mapping is provided.

FQBN mapping:
- Default file: tools/fqbn_map.json
- Override via env: MODULO_FQBN_MAP=/path/to/map.json
- Or CLI: --fqbn-map /path/to/map.json

Writes reports to: parity_reports/compile_sanity_<timestamp>/
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from export.emit import emit_project
from export.targets.registry import load_target


def _minimal_project(behavior_key: str, *, w: int = 16, h: int = 16) -> Dict[str, Any]:
    return {
        "version": 1,
        "layout": {"kind": "cells", "width": w, "height": h},
        "postfx": {},
        "layers": [
            {
                "name": behavior_key,
                "enabled": True,
                "behavior": behavior_key,
                "params": {},
                "purpose_f0": 0.0,
                "purpose_f1": 0.0,
                "purpose_i0": 0,
            }
        ],
    }


def _run(cmd: List[str], *, cwd: Path | None = None) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
        out = (p.stdout or "") + ("\n" + (p.stderr or "") if (p.stderr or "") else "")
        return int(p.returncode), out.strip()
    except FileNotFoundError:
        return 127, f"Missing executable: {cmd[0]}"
    except Exception as e:
        return 1, f"Failed to run {cmd}: {e}"


def _pick_targets() -> List[Tuple[str, str]]:
    return [
        ("arduino_uno_fastled_noneaudio", "arduino"),
        ("esp32_hub75_i2sdma_noneaudio", "platformio"),
        ("rp2040_fastled_noneaudio", "platformio"),
    ]


def _pick_behaviors() -> List[str]:
    return [
        "solid_color",
        "game_of_life",
        "tilemap_sprite",
    ]


def _load_fqbn_map(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return dict((data.get("mappings") or {}))
    except Exception:
        return {}


def _arduino_compile(ino_path: Path, *, fqbn: str) -> Tuple[int, str]:
    """Compile using arduino-cli.

    arduino-cli expects a *sketch folder* whose name matches the .ino.
    """
    stem = ino_path.stem
    with tempfile.TemporaryDirectory() as td:
        td_p = Path(td)
        sketch_dir = td_p / stem
        sketch_dir.mkdir(parents=True, exist_ok=True)
        (sketch_dir / ino_path.name).write_text(ino_path.read_text(encoding="utf-8"), encoding="utf-8")
        # Try compile. If cores aren't installed, arduino-cli will return non-zero with a helpful message.
        cmd = ["arduino-cli", "compile", "--fqbn", fqbn, "--warnings", "all", str(sketch_dir)]
        return _run(cmd)



def _load_fqbn_presets(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return dict((data.get("presets") or {}))
    except Exception:
        return {}


def _arduino_core_list() -> List[Dict[str, Any]]:
    """Return arduino-cli core list as JSON-ish.

    If the command fails or JSON output isn't supported, returns [].
    """
    try:
        rc, out = _run(["arduino-cli", "core", "list", "--format", "json"])
        if rc != 0:
            return []
        return json.loads(out) if out.strip().startswith("[") else []
    except Exception:
        return []


def _hint_install_core_for_fqbn(fqbn: str, installed_cores: List[Dict[str, Any]]) -> str:
    """Best-effort hint for installing the core that provides an FQBN.

    For third-party cores (esp32, rp2040, etc.) users may need to add an
    additional Boards Manager URL first; we avoid hardcoding URLs here.
    """
    prefix = fqbn.split(":")
    if len(prefix) >= 2:
        pkg = f"{prefix[0]}:{prefix[1]}"
    else:
        pkg = fqbn

    have = set()
    for c in installed_cores or []:
        # arduino-cli JSON typically includes fields like 'ID' or 'ID'/'id'
        cid = (c.get("ID") or c.get("id") or "").strip()
        if cid:
            have.add(cid)

    if pkg in have:
        return ""

    return (
        f"Missing core for '{pkg}'. Try:\n"
        f"  arduino-cli core update-index\n"
        f"  arduino-cli core install {pkg}\n"
        f"If that fails, add the vendor's Boards Manager URL, then re-run the install."
    )

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fqbn-map", default="", help="Path to fqbn_map.json (overrides MODULO_FQBN_MAP)")
    ap.add_argument("--preset", default="", help="Name of a preset in tools/fqbn_presets.json to merge into mappings")
    args = ap.parse_args()

    ts = _dt.datetime.utcnow().strftime("%Y%m%d_%H%M%SZ")
    out_dir = REPO_ROOT / "parity_reports" / f"compile_sanity_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    have_arduino = shutil.which("arduino-cli") is not None
    have_pio = shutil.which("pio") is not None

    # FQBN map
    fqbn_map_path = Path(args.fqbn_map) if args.fqbn_map else Path(
        ("" if "MODULO_FQBN_MAP" not in __import__("os").environ else __import__("os").environ["MODULO_FQBN_MAP"])
    )
    if not str(fqbn_map_path):
        fqbn_map_path = REPO_ROOT / "tools" / "fqbn_map.json"
    fqbn_map = _load_fqbn_map(fqbn_map_path)

    # Presets (optional)
    presets_path = REPO_ROOT / "tools" / "fqbn_presets.json"
    presets = _load_fqbn_presets(presets_path)
    if args.preset:
        preset = presets.get(args.preset) or {}
        # preset entries win only if mapping missing
        for k, v in preset.items():
            fqbn_map.setdefault(k, v)

    installed_cores: List[Dict[str, Any]] = _arduino_core_list() if have_arduino else []

    summary: Dict[str, Any] = {
        "timestamp": ts,
        "have_arduino_cli": have_arduino,
        "have_platformio": have_pio,
        "fqbn_map_path": str(fqbn_map_path),
        "fqbn_presets_path": str(presets_path),
        "fqbn_preset_used": args.preset,
        "fqbn_mappings": fqbn_map,
        "arduino_installed_cores": installed_cores,
        "runs": [],
    }

    for target_id, mode in _pick_targets():
        try:
            load_target(target_id)
        except Exception as e:
            summary["runs"].append({
                "target": target_id,
                "output_mode": mode,
                "status": "SKIP",
                "detail": f"Target not available: {e}",
            })
            continue

        for beh in _pick_behaviors():
            proj = _minimal_project(beh)
            stem = f"{target_id}__{beh}__{mode}"
            out_path = out_dir / stem

            try:
                written, _rep = emit_project(project=proj, out_path=out_path, target_id=target_id, output_mode=mode)
                written_p = Path(written)
            except Exception as e:
                summary["runs"].append({
                    "target": target_id,
                    "behavior": beh,
                    "output_mode": mode,
                    "status": "ERR",
                    "detail": f"Emit failed: {e}",
                })
                continue

            rec: Dict[str, Any] = {
                "target": target_id,
                "behavior": beh,
                "output_mode": mode,
                "emitted": str(written_p.relative_to(REPO_ROOT)) if written_p.exists() else str(written_p),
                "status": "OK",
                "compile": "N/A",
                "compile_hint": "",
            }

            if mode.startswith("platformio"):
                if have_pio and written_p.exists() and written_p.is_dir():
                    rc, out = _run(["pio", "run"], cwd=written_p)
                    rec["compile"] = "OK" if rc == 0 else "ERR"
                    if rc != 0:
                        rec["status"] = "WARN"
                        rec["detail"] = out[-2000:]
                else:
                    rec["compile"] = "SKIP"
            else:
                # Arduino sketch compilation
                if have_arduino and written_p.exists() and written_p.suffix.lower() == ".ino":
                    fqbn = fqbn_map.get(target_id, "")
                    if not fqbn and args.preset:
                        fqbn = fqbn_map.get(target_id, "")
                    if not fqbn:
                        rec["compile"] = "SKIP"
                        rec["compile_hint"] = f"No FQBN mapping for target_id '{target_id}'. Add it to tools/fqbn_map.json or use --preset."
                    else:
                        rc, out = _arduino_compile(written_p, fqbn=fqbn)
                        rec["compile"] = "OK" if rc == 0 else "ERR"
                        if rc != 0:
                            rec["status"] = "WARN"
                            rec["detail"] = out[-2000:]
                            hint = _hint_install_core_for_fqbn(fqbn, installed_cores)
                            if hint:
                                rec["compile_hint"] = hint
                else:
                    rec["compile"] = "SKIP"

            summary["runs"].append(rec)

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote: {out_dir}/summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
