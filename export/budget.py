from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

@dataclass
class BudgetEstimate:
    leds: int
    layers: int
    est_ram_bytes: int
    est_cpu_class: str
    notes: List[str]
    ram_limit_bytes: Optional[int] = None
    max_leds_recommended: Optional[int] = None
    max_leds_hard: Optional[int] = None

# Conservative defaults for classic AVR boards
UNO_RAM = 2048
MEGA_RAM = 8192

def _infer_led_count(project: Dict[str, Any]) -> int:
    # Prefer layout (Qt schema + legacy variants)
    layout = (project or {}).get("layout") or {}
    kind = str(layout.get("kind") or layout.get("shape") or "").strip().lower()
    if kind == "cells":
        kind = "matrix"
    if kind == "strip":
        return int(layout.get("count", layout.get("num_leds", layout.get("led_count", 60))) or 60)
    if kind == "matrix":
        w = int(layout.get("width", layout.get("matrix_w", layout.get("mw", 0))) or 0)
        h = int(layout.get("height", layout.get("matrix_h", layout.get("mh", 0))) or 0)
        if w > 0 and h > 0:
            return int(w * h)
    # Fall back to export section
    export = (project or {}).get("export") or {}
    return int(export.get("led_count", export.get("num_leds", 60)) or 60)


def _infer_layers(project: Dict[str, Any]) -> int:
    return len((project or {}).get("layers") or [])

def estimate_project_budget(project: Dict[str, Any]) -> BudgetEstimate:
    """Backward-compatible estimate using legacy 'export.board' heuristics."""
    export = (project or {}).get("export") or {}
    board = str(export.get("board", "uno")).lower()
    ram_limit = UNO_RAM if "uno" in board else (MEGA_RAM if "mega" in board else MEGA_RAM)
    return estimate_project_budget_for_limits(project, ram_limit_bytes=ram_limit, max_leds_recommended=None, max_leds_hard=None)

def estimate_project_budget_for_target(project: Dict[str, Any], target_meta: Dict[str, Any]) -> BudgetEstimate:
    """Estimate memory/CPU pressure against a specific target pack's declared limits."""
    ram_limit = target_meta.get("ram_limit_bytes")
    max_leds = target_meta.get("max_leds_recommended")
    max_leds_hard = target_meta.get("max_leds_hard")
    return estimate_project_budget_for_limits(project, ram_limit_bytes=ram_limit, max_leds_recommended=max_leds, max_leds_hard=max_leds_hard)

def estimate_project_budget_for_limits(
    project: Dict[str, Any],
    *,
    ram_limit_bytes: Optional[int],
    max_leds_recommended: Optional[int],
    max_leds_hard: Optional[int],
) -> BudgetEstimate:
    leds = _infer_led_count(project)
    layers = _infer_layers(project)
    notes: List[str] = []

    # Rough RAM model: LED framebuffer + scratch + per-led state + overhead.
    # This is intentionally conservative and is used for warnings/gates, not exact sizing.
    fb = leds * 3
    scratch = leds * 3
    per_led_state = leds
    overhead = 768
    est = fb + scratch + per_led_state + overhead

    cpu = "light"
    if layers >= 4 or leds >= 300:
        cpu = "medium"
    if layers >= 7 or leds >= 600:
        cpu = "heavy"

    if isinstance(max_leds_hard, int) and leds > max_leds_hard:
        notes.append(f"LED count {leds} exceeds target hard limit {max_leds_hard}.")

    if isinstance(max_leds_recommended, int) and leds > max_leds_recommended:
        notes.append(f"LED count {leds} exceeds target recommended max {max_leds_recommended}.")
    if isinstance(ram_limit_bytes, int) and est > ram_limit_bytes:
        notes.append(f"Estimated RAM {est} bytes > limit {ram_limit_bytes} bytes. Reduce LEDs/layers or choose a higher-RAM target.")
    if leds > 575:
        notes.append("High LED count: consider reducing layers/post-fx or using a higher-RAM board.")
    if layers > 10:
        notes.append("Many layers: consider merging layers or disabling heavy post-fx.")

    return BudgetEstimate(
        leds=leds,
        layers=layers,
        est_ram_bytes=est,
        est_cpu_class=cpu,
        notes=notes,
        ram_limit_bytes=ram_limit_bytes if isinstance(ram_limit_bytes, int) else None,
        max_leds_recommended=max_leds_recommended if isinstance(max_leds_recommended, int) else None,
        max_leds_hard=max_leds_hard if isinstance(max_leds_hard, int) else None,
    )
