"""Kernel export probe.

This is a small, safe, in-app proof that:
- a Kernel layer with params['cpp'] actually lands in the generated Arduino sketch
- the export template token replacement happened (no unreplaced {WRITE_LOOP_CASES})

It does NOT try to compile firmware. It is purely a codegen integrity check.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any, Dict, Optional

@dataclass
class KernelExportProbeResult:
    ok: bool
    summary: str
    evidence: Dict[str, Any]

def run_kernel_export_probe(*, target_id: str = "arduino_avr_fastled_noaudio") -> KernelExportProbeResult:
    """Generate an export and assert kernel cpp is present."""
    marker = "// KERNEL_EXPORT_PROBE_MARKER"
    cpp_body = "\n".join(
        [
            marker,
            "// must assign r/g/b in 0..1",
            "r = 1.0f;",
            "g = 0.0f;",
            "b = 0.0f;",
        ]
    )

    # Minimal project: strip surface, single kernel layer.
    from app.project_model import build_surface_dict

    project: Dict[str, Any] = {
        "surface": build_surface_dict(kind="strip", count=30),
        "layers": [
            {
                "id": "kernel_probe",
                "name": "Kernel Probe",
                "enabled": True,
                "opacity": 1.0,
                "blend_mode": "over",
                "behavior": "kernel",
                "kind": "kernel",
                "params": {
                    "cpp": cpp_body,
                    # Keep py present but unused for export.
                    "py": "def pixel(ctx):\n    return 255,0,0\n",
                    "budget_ms": 10.0,
                    "strike_limit": 3,
                    "deterministic": True,
                    "seed": 1234,
                },
            }
        ],
        "rules": [],
        "postfx": {},
    }

    try:
        from export.emit import emit_project

        with tempfile.TemporaryDirectory(prefix="modulo_kernel_export_probe_") as td:
            out_path = Path(td) / "kernel_probe.ino"
            written_path, report = emit_project(project=project, out_path=out_path, target_id=target_id, output_mode="arduino")
            txt = Path(written_path).read_text(encoding="utf-8", errors="replace")
            ok_marker = marker in txt
            ok_token = "{WRITE_LOOP_CASES}" not in txt
            ok_mapping = ("Kernel XY (mapping truth)" in txt) and ("MATRIX_SERPENTINE" in txt) and ("MATRIX_FLIP_X" in txt) and ("MATRIX_ROTATE" in txt)
            ok = bool(ok_marker and ok_token)
            summary = "PASS" if ok else "FAIL"
            if not ok_marker:
                summary = "FAIL: kernel marker not found in exported sketch"
            elif not ok_token:
                summary = "FAIL: {WRITE_LOOP_CASES} token not replaced"
            return KernelExportProbeResult(
                ok=ok,
                summary=summary,
                evidence={
                    "target_id": target_id,
                    "written_path": str(written_path),
                    "marker_found": ok_marker,
                    "token_replaced": ok_token,
                    "report_tail": str(report)[-800:],
                },
            )
    except Exception as e:
        try:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="EXPORT", code="KERNEL_EXPORT_PROBE_EXCEPTION", summary="kernel export probe exception", details={"target_id": target_id})
        except Exception:
            pass
        return KernelExportProbeResult(
            ok=False,
            summary="FAIL: exception during kernel export probe",
            evidence={"target_id": target_id, "exc": repr(e)},
        )
