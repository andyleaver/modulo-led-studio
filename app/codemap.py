"""Code location mapping for diagnostics.

Purpose
- Help users/devs find *where* to safely add/modify features.
- Provide stable anchors (file + line range) even when diagnostics pass.

Best-effort behavior
- If a symbol cannot be imported or inspected, its location is `None`.
- Absolute paths are preserved (they're the most actionable in a local checkout).
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class CodeLocation:
    file: str
    start_line: int
    end_line: int

    def fmt(self) -> str:
        if self.start_line <= 0:
            return f"{self.file}:?"
        if self.end_line and self.end_line >= self.start_line:
            return f"{self.file}:{self.start_line}-{self.end_line}"
        return f"{self.file}:{self.start_line}"


def _locate(obj: Any) -> Optional[CodeLocation]:
    """Return file + line range for a callable/class/module attribute."""
    try:
        # Unwrap methods / bound callables
        if hasattr(obj, "__func__"):
            obj = obj.__func__

        file = inspect.getsourcefile(obj) or inspect.getfile(obj)
        if not file:
            return None

        try:
            src_lines, start = inspect.getsourcelines(obj)
            end = start + len(src_lines) - 1
            return CodeLocation(file=file, start_line=int(start), end_line=int(end))
        except Exception:
            # Some objects have files but no retrievable source
            return CodeLocation(file=file, start_line=0, end_line=0)
    except Exception:
        return None


def build_codemap() -> Dict[str, Optional[CodeLocation]]:
    """Compute a codemap for the current running install."""

    items: List[Tuple[str, str]] = [
        ("entry.modulo_designer.main", "modulo_designer:main"),
        ("qt.run_qt", "qt.qt_app:run_qt"),
        ("qt.QtMainWindow", "qt.qt_app:QtMainWindow"),
        ("qt.CoreBridge", "qt.core_bridge:CoreBridge"),
        ("qt.CoreBridge._rebuild_full_preview_engine", "qt.core_bridge:CoreBridge._rebuild_full_preview_engine"),
        ("preview.PreviewEngine", "preview.preview_engine:PreviewEngine"),
        ("preview.PreviewEngine.render_frame", "preview.preview_engine:PreviewEngine.render_frame"),
        # Behavior/effect registration
        ("behaviors.registry.REGISTRY", "behaviors.registry:REGISTRY"),
        ("behaviors.registry.register", "behaviors.registry:register"),
        ("behaviors.registry.build_registry", "behaviors.registry:build_registry"),
        ("diagnostics.diagnose_project", "app.project_diagnostics:diagnose_project"),
        ("export.arduino_exporter.export_project_validated", "export.arduino_exporter:export_project_validated"),
        ('export.export_eligibility.get_eligibility', 'export.export_eligibility:get_eligibility'),
        ('preview.emit_contract', 'preview.preview_engine:PreviewEngine.render_frame'),
        ("params.ensure.ensure_params", "params.ensure:ensure_params"),
    ]

    out: Dict[str, Optional[CodeLocation]] = {}
    for label, spec in items:
        try:
            mod_name, sym = spec.split(":", 1)
            mod = __import__(mod_name, fromlist=[sym])
            obj = mod
            for part in sym.split("."):
                obj = getattr(obj, part)
            out[label] = _locate(obj)
        except Exception:
            out[label] = None

    # Best-effort fallback: if inspect/import failed, grep for a defining line.
    root = Path(__file__).resolve().parents[1]
    for label, spec in items:
        if out.get(label) is not None:
            continue
        try:
            mod_name, sym = spec.split(":", 1)
            # Translate module -> relative file path
            rel = Path(*mod_name.split("."))
            candidate = (root / rel).with_suffix(".py")
            if not candidate.exists():
                continue
            name = sym.split(".")[-1]
            # Search for common definers
            pat = re.compile(rf"^\s*(def|class)\s+{re.escape(name)}\b")
            for idx, line in enumerate(candidate.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                if pat.search(line):
                    out[label] = CodeLocation(file=str(candidate), start_line=idx, end_line=idx)
                    break
        except Exception:
            continue
    return out


def build_default_codemap() -> Dict[str, Optional[CodeLocation]]:
    """Backwards-compatible alias used by older UI code."""
    return build_codemap()


def format_codemap_section(codemap: Optional[Dict[str, Optional[CodeLocation]]] = None) -> List[str]:
    cm = codemap if codemap is not None else build_codemap()
    lines: List[str] = []
    lines.append("== CODE MAP (FILE:LINE-RANGE) ==")
    for k in sorted(cm.keys()):
        loc = cm[k]
        if loc is None:
            lines.append(f"{k}: ∅")
        else:
            lines.append(f"{k}: {loc.fmt()}")
    return lines


def get_effect_locations(effect_keys: List[str], *, max_items: int = 80) -> List[Tuple[str, Dict[str, Any]]]:
    """Best-effort map of effect keys to code locations.

    This is intentionally *not* a validator. The goal is to help contributors
    quickly jump to the right files/lines when adding or fixing features.

    Returns:
        List of tuples (effect_key, info) ordered by input order.
        info keys:
            - 'preview_emit': Optional[CodeLocation]
            - 'arduino_emit': Optional[CodeLocation]
            - 'definition': Optional[CodeLocation] (BehaviorDef class instance)
            - 'notes': Optional[str]
    """

    out: List[Tuple[str, Dict[str, Any]]] = []
    if not effect_keys:
        return out

    # De-dup while preserving order.
    seen = set()
    keys: List[str] = []
    for k in effect_keys:
        if k and k not in seen:
            seen.add(k)
            keys.append(k)
    keys = keys[: max_items]

    def _fmt(loc: Optional[CodeLocation]) -> Optional[str]:
        if loc is None:
            return None
        try:
            return loc.fmt()
        except Exception:
            return str(loc)

    try:
        from behaviors.registry import REGISTRY  # type: ignore
    except Exception as e:
        for k in keys:
            out.append((k, {"def": None, "preview_emit": None, "arduino_emit": None, "ok": False,
                            "notes": f"could_not_import_REGISTRY: {e}"}))
        return out

    for k in keys:
        info: Dict[str, Any] = {"def": None, "preview_emit": None, "arduino_emit": None, "ok": False, "notes": None}
        try:
            d = REGISTRY.get(k)
        except Exception:
            d = None
        if d is None:
            info["notes"] = "not_registered"
            out.append((k, info))
            continue

        info["ok"] = True

        info["def"] = _fmt(_locate(d.__class__))

        # preview_emit
        pe = getattr(d, "preview_emit", None)
        if pe is not None:
            info["preview_emit"] = _fmt(_locate(pe))

        # export emitters (names vary by era)
        ae = None
        for attr in ("arduino_emit", "export_emit", "emit_arduino"):
            if hasattr(d, attr):
                ae = getattr(d, attr)
                break
        if ae is not None:
            info["arduino_emit"] = _fmt(_locate(ae))

        out.append((k, info))

    return out