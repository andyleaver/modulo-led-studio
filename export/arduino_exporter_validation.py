from __future__ import annotations

import json
import re
from pathlib import Path

from runtime.resolver import resolve_project_postfx

TOKEN_RE = re.compile(r"@@[A-Z0-9_]+@@")
EXPORT_MARKER = "MODULO_EXPORT"


class ExportValidationError(Exception):
    pass

def validate_export_text(text: str) -> None:
    """
    Fail-closed exporter validation.

    - No unresolved @@TOKENS@@
    - No accidental python placeholders from UI/engine (e.g. {engine., {len()
    - No accidental double-brace artifacts ({{ or }})
    - Must include EXPORT_MARKER marker
    - Must include required defs markers
    """
    tokens = TOKEN_RE.findall(text)
    if tokens:
        raise ExportValidationError(f"Unresolved tokens found: {tokens}")

    for bad in ("{engine.", "{len("):
        if bad in text:
            raise ExportValidationError(f"Forbidden artifact found in export: {bad}")

    # Prove which exporter produced this .ino
    if EXPORT_MARKER not in text:
        raise ExportValidationError("Export missing EXPORT_MARKER marker")

    required_markers = [
        "state_reset_layer",
    ]
    missing = [m for m in required_markers if m not in text]
    if missing:
        raise ExportValidationError(f"Export missing required definitions: {missing}")

def export_sketch(*, sketch_code: str, template_path: Path, out_path: Path, replacements: dict | None = None) -> Path:
    """Write a sketch file by filling a token template.

    Token format is @@TOKEN@@.
    Always replaces @@SKETCH@@. Optional `replacements` can fill additional tokens.
    """
    tpl = Path(template_path).read_text(encoding="utf-8", errors="ignore")
    out = tpl.replace("@@SKETCH@@", str(sketch_code).rstrip() + "\n")

    if replacements:
        # Replace in a deterministic order for easier debugging.
        # Multi-pass so tokens introduced by expansions (e.g. LED_IMPL blocks) get replaced too.
        for _pass in range(3):
            changed = False
            for k in sorted(replacements.keys()):
                token = f"@@{k}@@"
                v = str(replacements[k])
                if token in out:
                    out2 = out.replace(token, v)
                    if out2 != out:
                        changed = True
                        out = out2
            if not changed:
                break
    validate_export_text(out)
    Path(out_path).write_text(out, encoding="utf-8")
    return Path(out_path)

def _load_target_hooks(template_path: Path | None) -> dict:
    """Load optional low-level hook snippets from a target pack's target.json.

    If template_path lives under export/targets/<id>/, we look for sibling target.json.
    Schema:
      "hooks": {
          "extra_includes": "...",
          "extra_defines": "...",
          "prelude_cpp": "...",
          "setup_cpp": "...",
          "loop_begin_cpp": "...",
          "loop_end_cpp": "..."
      }
    All fields are optional and default to "".
    """
    hooks = {}
    if not template_path:
        return hooks
    try:
        tp = Path(template_path)
        tj = tp.parent / "target.json"
        if not tj.exists():
            return hooks
        meta = json.loads(tj.read_text(encoding="utf-8", errors="ignore") or "{}")
        hooks = meta.get("hooks") or {}
        if not isinstance(hooks, dict):
            return {}
        # Normalize to strings
        out = {}
        for k in ("extra_includes","extra_defines","prelude_cpp","setup_cpp","loop_begin_cpp","loop_end_cpp"):
            v = hooks.get(k, "")
            out[k] = str(v) if v is not None else ""
        return out
    except Exception:
        return {}

def _inject_target_hooks(sketch_code: str, hooks: dict) -> str:
    """Inject low-level target hook snippets into generated sketch code."""
    if not hooks:
        return sketch_code

    extra_includes = hooks.get("extra_includes","").rstrip()
    extra_defines  = hooks.get("extra_defines","").rstrip()
    prelude_cpp    = hooks.get("prelude_cpp","").rstrip()
    setup_cpp      = hooks.get("setup_cpp","").rstrip()
    loop_begin_cpp = hooks.get("loop_begin_cpp","").rstrip()
    loop_end_cpp   = hooks.get("loop_end_cpp","").rstrip()

    code = str(sketch_code)

    # Header injection: put includes/defines/prelude at top of the sketch code
    header_bits = []
    if extra_includes:
        header_bits.append("// --- TARGET EXTRA INCLUDES ---\n" + extra_includes + "\n")
    if extra_defines:
        header_bits.append("// --- TARGET EXTRA DEFINES ---\n" + extra_defines + "\n")
    if prelude_cpp:
        header_bits.append("// --- TARGET PRELUDE ---\n" + prelude_cpp + "\n")
    if header_bits:
        code = "\n".join(header_bits) + "\n" + code.lstrip()

    # Setup injection: after the opening brace of setup()
    if setup_cpp:
        code = re.sub(r"(void\s+setup\s*\(\s*\)\s*\{\s*)",
                      r"\1\n  // --- TARGET SETUP HOOK ---\n" + "\n".join("  "+ln if ln.strip() else "" for ln in setup_cpp.splitlines()) + "\n",
                      code, count=1)

    # Loop injections: begin/end
    if loop_begin_cpp:
        code = re.sub(r"(void\s+loop\s*\(\s*\)\s*\{\s*)",
                      r"\1\n  // --- TARGET LOOP BEGIN HOOK ---\n" + "\n".join("  "+ln if ln.strip() else "" for ln in loop_begin_cpp.splitlines()) + "\n",
                      code, count=1)

    if loop_end_cpp:
        # insert just before the final closing brace of loop (best-effort)
        code = re.sub(r"(\n\}\s*\n\s*)$",
                      "\n  // --- TARGET LOOP END HOOK ---\n" + "\n".join("  "+ln if ln.strip() else "" for ln in loop_end_cpp.splitlines()) + "\n\1",
                      code, count=1)

    return code

