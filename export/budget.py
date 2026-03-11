from __future__ import annotations
from app.project_model import get_surface_spec
from core.surface_compat import build_surface_geometry_dict, get_surface_mapping_values
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

def _infer_count(project: Dict[str, Any]) -> int:
    spec = get_surface_spec(project or {})
    if spec is not None and int(getattr(spec, "count", 0) or 0) > 0:
        return int(spec.count)
    export = (project or {}).get("export") or {}
    return int(export.get("count", 60) or 60)

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
    leds = _infer_count(project)
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

# Exporters should consume SurfaceSpec via:
#   from app.project_model import get_surface_spec
#   spec = get_surface_spec(project)
# This prevents preview/export geometry divergence.

# ------------------------------------------------------------------
# All exporters must use SurfaceSpec for geometry truth
# ------------------------------------------------------------------
def _surface_geometry(project):
    spec = _get_surface_spec(project) if "_get_surface_spec" in globals() else get_surface_spec(project)
    if not spec:
        raise RuntimeError("SurfaceSpec missing — export blocked.")
    return build_surface_geometry_dict(spec, default_kind="strip", default_count=60)


# ------------------------------------------------------------------
# Legacy layout-based geometry access is deprecated.
# Exporters must NOT read project.surface.shape/width/height directly.
# Geometry authority = SurfaceSpec via get_surface_spec().
# ------------------------------------------------------------------
