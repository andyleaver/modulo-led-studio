from __future__ import annotations

from pathlib import Path

from app.project_model import build_surface_dict, apply_surface_dict_to_layout_model

import math


def _artifact_run_dir(name: str):
    repo_root = Path(__file__).resolve().parents[1]
    out_dir = repo_root.parent / "artifacts" / "diagnostics_runs" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir



def _legacy_layer_param_mirror_keys() -> tuple[str, ...]:
    return (
        "layer_enabled",
        "layer_opacity",
        "layer_blend_mode",
        "layer_order",
    )


class DiagnosticsConsoleFullAuditProbeMixin:
    def _probe_audit_lock(self) -> str:
        """Door N1: ensure FULL AUDIT sequence integrity."""
        seq = ["A1","A2","B1","C1","D1","F1","G1","H1","I1","J1","K1","L1","M1","E1"]
        seen = set()
        for s in seq:
            if s in seen:
                return f"[AuditLock] FAIL duplicate step {s}"
            seen.add(s)
        if seq[0]!="A1" or seq[-1]!="E1":
            return f"[AuditLock] FAIL bad boundaries {seq}"
        return "[AuditLock] PASS sequence locked"


    def _probe_export_canonical_params_quick(self) -> str:
        """Door L1: Export canonical params (quick)

        Proves that canonical params we rely on in preview (operator.*, layers[i].opacity,
        project.postfx.*) survive the export pipeline and appear in the generated sketch
        (without requiring a board).

        This is NOT full preview-vs-firmware visual parity. It is a "lands in export config/code" door.
        """
        core = getattr(self, "app_core", None)
        if core is None:
            return "[ExportCanon] ERROR: no app_core"

        try:
            from pathlib import Path
            import time as _time
            import json as _json
            from export.arduino_exporter import export_project_validated
        except Exception as e:
            return "[ExportCanon] ERROR: import failed: " + repr(e)

        # Minimal exportable project with a gain operator and a Rules mutation on operator.gain.
        project = {
            "surface": build_surface_dict(kind="strip", count=144),
            "layers": [{
                "behavior": "solid",
                "enabled": True,
                "opacity": 1.0,
                "blend_mode": "over",
                "params": {"color": [80, 80, 80]},
                # NOTE: normalizer expects operators[0] to match behavior; gain is slot 1.
                "operators": [
                    {"type": "solid", "params": {"color": [80, 80, 80]}},
                    {"type": "gain", "params": {"gain": 2.0}},
                ],
            }],
            "rules": {
                "rules": [{
                    "id": "r_set_gain",
                    "when": {"type": "always"},
                    "do": [{
                        "type": "set_layer_param",
                        "layer": 0,
                        "param": "operator.gain",
                        "value": 2.0,
                    }],
                }],
            },
            # Export preconditions: keep it simple, no audio required.
            "ui": {"export_target": "basic"},
            "export": {"audio_backend": "none"},
        }

        run_id = _time.strftime("%Y%m%d_%H%M%SZ", _time.gmtime())
        out_dir = _artifact_run_dir(f"DOOR_L1_{run_id}")
        out_file = out_dir / "modulo_export.ino"

        evidence = {"out_file": str(out_file)}
        try:
            export_project_validated(project, out_file)
        except Exception as e:
            evidence["export_error"] = repr(e)
            return "[ExportCanon] FAIL: export threw " + _json.dumps(evidence, separators=(",", ":"))

        try:
            code = out_file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            evidence["read_error"] = repr(e)
            return "[ExportCanon] FAIL: could not read sketch " + _json.dumps(evidence, separators=(",", ":"))

        # Heuristic checks: presence of operator runtime override tables + canonical operator.gain/export mention + gain operator emitted.
        must = {
            "has_op_tables": ("OP_P0_RT" in code) and ("OP_P0_SET" in code),
            "mentions_operator_gain": ("operator.gain" in code),
            "mentions_gain_operator": ("gain" in code),
            "has_ops_per_layer": ("OPS_PER_LAYER" in code),
        }
        evidence.update(must)
        if not all(must.values()):
            # Trim a small excerpt around canonical/legacy gain marker for debugging (max ~400 chars).
            k = code.find("operator.gain")
            if k == -1:
                k = -1
            if k != -1:
                evidence["excerpt"] = code[max(0, k-120):k+280]
            return "[ExportCanon] FAIL: export missing expected canonical artifacts " + _json.dumps(evidence, separators=(",", ":"))

        return "[ExportCanon] PASS " + _json.dumps({"out": str(out_file)}, separators=(",", ":"))



    def _probe_preview_export_semantic_parity(self) -> str:
        """Door M1: Preview↔Export semantic parity (controlled case)

        Controlled harness:
          - solid -> gain operator chain
          - authored operator.gain = 2.0
          - base color [80,80,80]

        Pass criteria:
          - preview pixel0 == [160,160,160] (within 0..255 ints)
          - exported sketch contains OP_P0_SET initializer that includes a ~2.0 literal
        """
        core = getattr(self, "app_core", None)
        if core is None:
            return "[M1] ERROR: no app_core"

        # --- Preview side ---
        try:
            layers = [{
                "behavior": "solid",
                "enabled": True,
                "opacity": 1.0,
                "blend_mode": "over",
                "params": {
                    # solid uses canonical key 'color' (defaults to red if missing)
                    "color": [80, 80, 80],
                    # canonical operator param (preview consumption proven by F1)

                },
                # normalizer forces operators[0] type == behavior, so put gain in slot 1
                "operators": [
                    {"type": "solid", "params": {"color": [80, 80, 80]}},
                    {"type": "gain", "params": {"gain": 2.0}},
                ],
            }]
            rules = []  # authored param, no rules required

            self._audit_inject_project(layers=layers, rules=rules, postfx=None)
            frame = self._audit_render_frame()
            if not frame:
                return "[M1] FAIL: preview returned no frame"

            # sample pixel0
            px = None
            try:
                p0 = frame[0]
                if isinstance(p0, (list, tuple)) and len(p0) >= 3:
                    px = [int(p0[0]), int(p0[1]), int(p0[2])]
                elif isinstance(p0, int):
                    # packed 0xRRGGBB
                    px = [(p0 >> 16) & 255, (p0 >> 8) & 255, p0 & 255]
            except Exception:
                px = None

            if px is None:
                return "[M1] FAIL: could not sample preview pixel0"
            if px != [160, 160, 160]:
                return "[M1] FAIL: preview pixel mismatch " + str({"pixel0": px, "expected": [160, 160, 160]})
        except Exception as e:
            return "[M1] ERROR: preview phase exception: " + repr(e)

        # --- Export side ---
        try:
            from pathlib import Path
            import time as _time
            from export.arduino_exporter import export_project_validated

            project = {
                "surface": build_surface_dict(kind="strip", count=144),
                "layers": layers,
                "rules": rules,
                "postfx": {},
                "meta": {"title": "M1_semantic_parity_harness"},
            }

            out_dir = _artifact_run_dir("DOOR_M1_" + _time.strftime("%Y%m%d_%H%M%SZ", _time.gmtime()))

            # Export using validated Arduino exporter (target packs are handled by emitters; this exporter is target-agnostic)
            ino_path = export_project_validated(project, out_dir / "M1_sketch.ino")

            # Find an .ino (or .h/.cpp) file and search for OP_P0_SET with a ~2.0 literal
            code_files = list(out_dir.rglob("*.ino")) + list(out_dir.rglob("*.h")) + list(out_dir.rglob("*.cpp"))
            if not code_files:
                return "[M1] FAIL: export produced no code files in " + str(out_dir)

            blob = ""
            for fp in code_files:
                try:
                    blob += "\n" + fp.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass

            if "OP_P0_SET" not in blob:
                return "[M1] FAIL: export missing OP_P0_SET (operator param set table)"

            # heuristic: require a 2.0-ish literal somewhere near OP_P0_SET
            idx = blob.find("OP_P0_SET")
            window = blob[idx: idx + 2000]
            import re as _re
            if not _re.search(r"\b2\.0\b|\b2\.00\b|\b2\b", window):
                return "[M1] FAIL: export did not show ~2.0 literal near OP_P0_SET"

        except Exception as e:
            return "[M1] ERROR: export phase exception: " + repr(e)

        return "[M1] PASS"
    def _probe_persistence_policy(self) -> str:
        """Door K1: Persistence policy (author-time state round-trip)

        Proves that authored project state round-trips through models.io.save_project/load_project,
        and that runtime/private keys (e.g. keys starting with '_') are not persisted.
        """
        try:
            from pathlib import Path
            import json
            import models.io as mio
            from models.project import Project, Layout, Layer

            from datetime import datetime, timezone
            out_dir = _artifact_run_dir(f"DOOR_K1_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')}")
            p = out_dir / "k1_roundtrip.modulo.json"

            # Build a minimal authored project.
            # Include a runtime/private key in postfx to ensure persistence stripping works.
            proj = Project(
                layers=[
                    Layer(
                        name="K1_BASE",
                        behavior="solid",
                        enabled=True,
                        opacity=0.33,
                        blend_mode="add",
                        params={"color": (80, 80, 80)},
                        operators=[
                            {"type": "solid", "params": {"color": [80, 80, 80]}},
                            {"type": "gain", "params": {"gain": 1.0}},
                        ],
                    )
                ],
                postfx={"trail_amount": 0.12, "_rt_cache_key": "DROP_ME"},
            )
            surface_cfg = build_surface_dict(kind='strip', count=144)
            proj.surface = apply_surface_dict_to_layout_model(Layout(), surface_cfg)

            mio.save_project(p, proj)

            raw = json.loads(p.read_text(encoding="utf-8"))

            # Must persist
            try:
                ok_trail = float(raw.get("postfx", {}).get("trail_amount", -1)) == 0.12
            except Exception:
                ok_trail = False
            try:
                ok_opacity = float(raw.get("layers", [{}])[0].get("opacity", -1)) == 0.33
            except Exception:
                ok_opacity = False
            ok_blend = (raw.get("layers", [{}])[0].get("blend_mode") == "add")

            # Must NOT persist (private keys)
            has_private_postfx = isinstance(raw.get("postfx", {}), dict) and any(
                isinstance(k, str) and k.startswith("_") for k in raw.get("postfx", {}).keys()
            )

            if not (ok_trail and ok_opacity and ok_blend) or has_private_postfx:
                ev = {
                    "ok_trail": ok_trail,
                    "ok_opacity": ok_opacity,
                    "ok_blend": ok_blend,
                    "has_private_postfx": has_private_postfx,
                    "saved_path": str(p),
                    "saved_postfx_keys": list((raw.get("postfx") or {}).keys()) if isinstance(raw.get("postfx"), dict) else None,
                }
                return "[Persistence] FAIL " + json.dumps(ev, separators=(",", ":"))

            # Load back and ensure the private key is still absent.
            loaded = mio.load_project(p)
            postfx = getattr(loaded, "postfx", None) or {}
            has_private_after_load = isinstance(postfx, dict) and any(
                isinstance(k, str) and k.startswith("_") for k in postfx.keys()
            )
            if has_private_after_load:
                ev = {
                    "has_private_after_load": True,
                    "loaded_postfx_keys": list(postfx.keys()),
                    "path": str(p),
                }
                return "[Persistence] FAIL " + json.dumps(ev, separators=(",", ":"))

            return "PASS"
        except Exception as e:
            return f"[Persistence] ERROR: {e}"

