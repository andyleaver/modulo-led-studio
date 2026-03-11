from __future__ import annotations
from app.project_model import get_surface_spec, get_surface_snapshot
from core.surface_compat import build_surface_geometry_dict, get_surface_mapping_values
import re
import math
from export.preconditions import check as _check_preconditions
from pathlib import Path
from typing import Tuple
from params.purpose_contract import ensure as ensure_purpose, clamp as clamp_purpose

# Exportable surface matrix (single source of truth)
from export.exportable_surface import RULES_LAYER_PARAMS_EXPORTABLE
from export.export_eligibility import get_eligibility, ExportStatus

from export.arduino_exporter_blocks import (
    TOKEN_RE,
    EXPORT_MARKER,
    _emit_postfx_blocks,
    _emit_rules_blocks,
    _runtime_state_h,
    _arduino_clamp_expr,
    _norm_audio_source,
)
from export.arduino_exporter_validation import (
    ExportValidationError,
    validate_export_text,
    export_sketch,
    _load_target_hooks,
    _inject_target_hooks,
)

from export.arduino_exporter_templates import (
    make_solid_sketch,
    make_solid_layers_sketch,
    apply_audio_export_config,
    make_external_audio_streamer_sketch,
)

from export.arduino_exporter_project import (
    export_project_layerstack_impl,
    validate_project_layout_compat_impl,
    export_project_validated_impl,
    export_project_impl,
)

from export.arduino_exporter_layerstack import make_layerstack_sketch
def export_project_layerstack(*, project: dict, template_path, out_path, replacements: dict | None = None):
    return export_project_layerstack_impl(
        project=project,
        template_path=template_path,
        out_path=out_path,
        replacements=replacements,
        make_layerstack_sketch_fn=make_layerstack_sketch,
        fastled_led_impl=FASTLED_LED_IMPL,
        matrix_impl=MATRIX_IMPL,
    )


def validate_project_layout_compat(project: dict) -> None:
    return validate_project_layout_compat_impl(project)


def export_project_validated(project: dict, out_path: Path, *, template_path: Path | None = None, replacements: dict | None = None) -> Path:
    return export_project_validated_impl(
        project,
        out_path,
        template_path=template_path,
        replacements=replacements,
        export_project_layerstack_fn=export_project_layerstack,
        fastled_led_impl=FASTLED_LED_IMPL,
    )


def export_project(*, project: dict, out_path: Path, template_path: Path | None = None):
    return export_project_impl(
        project=project,
        out_path=out_path,
        template_path=template_path,
        export_project_validated_fn=export_project_validated,
    )

FASTLED_LED_IMPL = r"""
#ifndef MODULO_LED_IMPL_KIND
#define MODULO_LED_IMPL_KIND "fastled"
#endif
#ifndef MODULO_LED_IMPL_LABEL
#define MODULO_LED_IMPL_LABEL "FastLED"
#endif
"""

NEOPIXELBUS_LED_IMPL_ESP32 = r"""
#ifndef MODULO_LED_IMPL_KIND
#define MODULO_LED_IMPL_KIND "neopixelbus_esp32"
#endif
#ifndef MODULO_LED_IMPL_LABEL
#define MODULO_LED_IMPL_LABEL "NeoPixelBus ESP32"
#endif
"""

HUB75_LED_IMPL_ESP32 = r"""
#ifndef MODULO_LED_IMPL_KIND
#define MODULO_LED_IMPL_KIND "hub75_esp32"
#endif
#ifndef MODULO_LED_IMPL_LABEL
#define MODULO_LED_IMPL_LABEL "HUB75 ESP32"
#endif
"""

MATRIX_IMPL = r"""

// Matrix layout
#define MATRIX_WIDTH @@MATRIX_WIDTH@@
#define MATRIX_HEIGHT @@MATRIX_HEIGHT@@
#define MATRIX_SERPENTINE @@MATRIX_SERPENTINE@@
#define MATRIX_ORIGIN "@@MATRIX_ORIGIN@@"
#define MATRIX_ROTATE @@MATRIX_ROTATE@@  // 0, 90, 180, 270
#define MATRIX_FLIP_X @@MATRIX_FLIP_X@@  // 0/1
#define MATRIX_FLIP_Y @@MATRIX_FLIP_Y@@  // 0/1

// Helper: use mapped indices when writing LEDs
#define MODULA_LED(i) leds[modulo_map_index((uint16_t)(i))]

// Map (x,y) -> linear index, applying origin + serpentine.
static inline uint16_t modulo_xy(uint16_t x, uint16_t y) {

  // origin transform
  if (strcmp(MATRIX_ORIGIN, "top_right") == 0 || strcmp(MATRIX_ORIGIN, "TR") == 0) {
    x = (MATRIX_WIDTH - 1) - x;
  } else if (strcmp(MATRIX_ORIGIN, "bottom_left") == 0 || strcmp(MATRIX_ORIGIN, "BL") == 0) {
    y = (MATRIX_HEIGHT - 1) - y;
  } else if (strcmp(MATRIX_ORIGIN, "bottom_right") == 0 || strcmp(MATRIX_ORIGIN, "BR") == 0) {
    x = (MATRIX_WIDTH - 1) - x;
    y = (MATRIX_HEIGHT - 1) - y;
  } else {
    // top_left (default)
  }

// Optional: rotate/flip logical coordinates before serpentine/origin mapping.
// NOTE: For 90/270, best results when MATRIX_WIDTH==MATRIX_HEIGHT or when the project dimensions
// already reflect the rotated physical orientation. Values are clamped for safety.
#if (MATRIX_ROTATE == 90)
  { uint16_t _tx = x; x = (uint16_t)((MATRIX_HEIGHT - 1) - y); y = _tx; }
#elif (MATRIX_ROTATE == 180)
  x = (uint16_t)((MATRIX_WIDTH - 1) - x);
  y = (uint16_t)((MATRIX_HEIGHT - 1) - y);
#elif (MATRIX_ROTATE == 270)
  { uint16_t _tx = x; x = y; y = (uint16_t)((MATRIX_WIDTH - 1) - _tx); }
#else
  // 0
#endif

#if MATRIX_FLIP_X
  x = (uint16_t)((MATRIX_WIDTH - 1) - x);
#endif
#if MATRIX_FLIP_Y
  y = (uint16_t)((MATRIX_HEIGHT - 1) - y);
#endif

  if (x >= MATRIX_WIDTH) x = MATRIX_WIDTH - 1;
  if (y >= MATRIX_HEIGHT) y = MATRIX_HEIGHT - 1;

  uint16_t row = y;
  if (MATRIX_SERPENTINE && (row & 1)) {
    return (row * MATRIX_WIDTH) + (MATRIX_WIDTH - 1 - x);
  } else {
    return (row * MATRIX_WIDTH) + x;
  }
}

// Map logical linear index -> physical linear index.
static inline uint16_t modulo_map_index(uint16_t i) {
  uint16_t n = (uint16_t)(MATRIX_WIDTH * MATRIX_HEIGHT);
  if (i >= n) return i;
  uint16_t x = (uint16_t)(i % MATRIX_WIDTH);
  uint16_t y = (uint16_t)(i / MATRIX_WIDTH);
  return modulo_xy(x, y);
}

"""

# Back-compat alias for target packs expecting NEOPIXELBUS_LED_IMPL
NEOPIXELBUS_LED_IMPL = NEOPIXELBUS_LED_IMPL_ESP32

# Exporters should consume SurfaceSpec via:
#   from app.project_model import get_surface_spec, get_surface_snapshot
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
