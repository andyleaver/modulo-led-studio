from __future__ import annotations

"""
Unified export emitter entrypoint.

- Resolves backends + hw config using export.targets.registry helpers
- Delegates code generation to the selected target emitter module
- Writes final artifact (.ino or .zip) into out_path.parent
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple
import zipfile


def _validate_export_artifact_text(text: str) -> list[str]:
    """Fail-loud validation for generated artifacts.

    We are preventing silent export corruption caused by unreplaced template tokens
    or accidental Python formatting artifacts.

    Returns list of problems (empty => OK).
    """
    probs = []
    t = text or ""
    # Unreplaced @@TOKENS@@
    try:
        import re
        toks = sorted(set(re.findall(r"@@[A-Z0-9_]+@@", t)))
        if toks:
            probs.append("Unreplaced template tokens: " + ", ".join(toks[:50]) + (f" …(+{len(toks)-50})" if len(toks) > 50 else ""))
    except Exception:
        pass

    # Accidental Python format/f-string artifacts
    suspicious = ["{engine.", "{len(", "{self.", "{project", "{ir.", "{selection", "{hw", "{aud", "{{", "}}"]
    found = [s for s in suspicious if s in t]
    if found:
        probs.append("Suspicious formatting artifacts found: " + ", ".join(found))

    # Common placeholder strings
    for s in ["REPLACE_ME", "TODO_TOKEN", "TEMPLATE_TOKEN"]:
        if s in t:
            probs.append(f"Placeholder '{s}' still present")

    return probs


def _validate_written_artifact(path: Path) -> None:
    """Validate the emitted file before we consider export successful."""
    try:
        if not path.exists() or not path.is_file():
            return
        if path.suffix.lower() not in (".ino", ".h", ".hpp", ".c", ".cpp", ".txt"):
            return
        txt = path.read_text(encoding="utf-8", errors="replace")
        probs = _validate_export_artifact_text(txt)
        if probs:
            # Delete corrupt output to prevent false success.
            try:
                path.unlink()
            except Exception:
                pass
            raise RuntimeError("Export validation failed:\n- " + "\n- ".join(probs))
    except Exception:
        raise


from export.targets.registry import (
    load_target,
    resolve_requested_backends,
    resolve_requested_hw,
    resolve_requested_audio_hw,
)


@dataclass
class EmitResult:
    written_path: Path
    report_text: str


def emit_project(*, project: Dict[str, Any], out_path: Path, target_id: str, output_mode: str) -> Tuple[Path, str]:
    out_path = Path(out_path)
    output_mode = str(output_mode or "arduino").strip().lower()

    target = load_target(target_id)
    meta = getattr(target, "meta", None) or {}

    # Resolve selection + hardware
    selection = resolve_requested_backends(project or {}, meta)
    hw = resolve_requested_hw(project or {}, meta)
    aud = resolve_requested_audio_hw(project or {}, meta, selection.get("audio_backend"))

    # Validate msg eq7 audio hw required (already also in parity gates in some builds, but keep fail-closed)
    if (selection.get("audio_backend") or "").lower() == "msgeq7":
        missing = []
        for k in ("msgeq7_reset_pin","msgeq7_strobe_pin","msgeq7_left_pin","msgeq7_right_pin"):
            if not str((aud or {}).get(k) or "").strip():
                missing.append(k)
        if missing:
            raise RuntimeError("Missing required MSGEQ7 audio_hw fields after resolve: " + ", ".join(missing))

    # Delegate to target emitter
    if not hasattr(target, "emit") or not callable(getattr(target, "emit")):
        raise RuntimeError(f"Target '{target_id}' missing emit(project, out_path, output_mode, selection, hw, audio_hw)")

    from export.ir import ShowIR
    ir = ShowIR.from_project(project, selection, hw, aud)
    written, rep = target.emit(
        ir=ir,
        out_path=out_path,
        output_mode=output_mode,
        selection=selection,
        hw=hw,
        audio_hw=aud,
    )
    written_p = Path(written)
    rep = str(rep or "")

    # Release R8: fail-loud validation of generated artifacts
    _validate_written_artifact(written_p)

    # If the target emitted a PlatformIO folder and the caller requested a zip, zip it here (single authority).
    if output_mode.startswith("platformio") or output_mode in ("pio_zip",):
        if written_p.exists() and written_p.is_dir():
            zip_path = out_path.parent / (out_path.stem + ".zip")
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for fp in written_p.rglob("*"):
                    if fp.is_file():
                        zf.write(fp, arcname=str(fp.relative_to(written_p)))
            rep = rep + f"\nFinal artifact: {zip_path.name} (zipped PlatformIO project)\n"
            return zip_path, rep

    return written_p, rep
