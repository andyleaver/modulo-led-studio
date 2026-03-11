from __future__ import annotations

from pathlib import Path
from typing import Tuple
import json

from ...ir import ShowIR
from ...arduino_exporter import export_project_validated, HUB75_LED_IMPL_ESP32
from ..registry import resolve_requested_hw
from app.project_model import get_surface_spec
from core.surface_compat import get_surface_mapping_values


def _get_meta() -> dict:
    try:
        return json.loads((Path(__file__).resolve().parent / "target.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def emit(*, ir: ShowIR, out_path: Path, **_kwargs) -> Tuple[Path, str]:
    """ESP32 HUB75 (I2S-DMA) target pack (cells-only, no-audio)."""
    tpl = Path(__file__).resolve().parent / "arduino_template.ino.tpl"
    meta = _get_meta()

    hw = resolve_requested_hw(ir.project, meta)

    # HUB75 config is canonical-only: project.export.hub75.* or target defaults.
    # Legacy ui.export_hub75_* keys are migration-only and must not be read here.
    proj = ir.project or {}
    exp = (proj.get("export") or {}) if isinstance(proj, dict) else {}
    hub = exp.get("hub75") or {}
    if not isinstance(hub, dict):
        hub = {}

    defs = ((meta.get("capabilities") or {}).get("defaults") or {})

    def gv(key: str, default: str) -> str:
        v = hub.get(key)
        if v is None:
            v = defs.get(f"hub75_{key}", meta.get(f"default_hub75_{key}", default))
        return str(v)

    panel_x = int(float(gv("panel_res_x", "64")))
    panel_y = int(float(gv("panel_res_y", "32")))
    chain = int(float(gv("chain", "1")))

    # Brightness + gamma output options
    hub75_brightness = int(float(gv("brightness", str(hw.get("brightness", 96)))))
    hub75_use_gamma = int(float(gv("use_gamma", "0")))
    hub75_gamma = gv("gamma", "2.2f")

    # Optional HUB75 output tweaks
    hub75_color_order = int(float(gv("color_order", "0")))
    hub75_debug_mode = int(float(gv("debug_mode", "0")))
    hub75_backend_ver = str(meta.get("hub75_backend_version") or "v0.1")

    # Fail-closed: this target expects canonical surface truth from SurfaceSpec.
    # Runtime/export must not derive cells truth from raw project.surface or leaked root layout residue.
    spec = get_surface_spec(proj)
    if spec is None:
        return (out_path, "BLOCKED: HUB75 target requires a canonical surface spec.")
    kind = str(getattr(spec, "kind", "") or "").lower().strip()
    if kind != "cells":
        return (out_path, f"BLOCKED: HUB75 target requires canonical cells surface truth (resolved kind={kind!r}).")

    # Rotation/flip remain target-local export options only; geometry stays on SurfaceSpec.
    hwmat = exp.get("hw") or {}
    m = (hwmat.get("matrix") or {}) if isinstance(hwmat, dict) else {}
    mw = int(getattr(spec, "width", 0) or 0)
    mh = int(getattr(spec, "height", 0) or 0)

    rot = int(m.get("rotate") or 0)
    flip_x = int(m.get("flip_x") or 0)
    flip_y = int(m.get("flip_y") or 0)

    inferred = []
    if panel_x <= 0:
        panel_x = 64
    if panel_y <= 0:
        panel_y = 32
    if chain <= 0:
        chain = 1
    if mw > 0 and panel_x > 0 and mw != panel_x * chain and (mw % panel_x) == 0:
        new_chain = mw // panel_x
        if new_chain > 0:
            inferred.append(f"chain {chain}->{new_chain}")
            chain = int(new_chain)
    if mh > 0 and panel_y > 0 and mh != panel_y and (mh % panel_y) == 0:
        inferred.append(f"vertical_panels={mh // panel_y} (not supported)")
    inferred_note = "; ".join(inferred) if inferred else ""

    if mw <= 0 or mh <= 0:
        return (out_path, "BLOCKED: HUB75 target requires canonical cells width/height from SurfaceSpec.")
    if mw != panel_x * chain:
        return (out_path, f"BLOCKED: cells width ({mw}) must equal panel_res_x*chain ({panel_x}*{chain}={panel_x * chain}).")
    if mh != panel_y:
        return (out_path, f"BLOCKED: cells height ({mh}) must equal panel_res_y ({panel_y}). Vertical chaining not enabled in this pack.")

    replacements = {
        "USE_MSGEQ7": "0",
        "LED_IMPL": HUB75_LED_IMPL_ESP32,
        # These are unused by HUB75 LED_IMPL but template expects them; keep harmless defaults.
        "DATA_PIN": str(hw.get("data_pin", "5")),
        "LED_TYPE": str(hw.get("led_type", "WS2812B")),
        "COLOR_ORDER": str(hw.get("color_order", "GRB")),
        "LED_BRIGHTNESS": str(hw.get("brightness", "96")),
        # HUB75 tokens
        "HUB75_PANEL_RES_X": str(panel_x),
        "HUB75_PANEL_RES_Y": str(panel_y),
        "HUB75_CHAIN": str(chain),
        "HUB75_BRIGHTNESS": str(hub75_brightness),
        "HUB75_USE_GAMMA": str(1 if hub75_use_gamma else 0),
        "HUB75_GAMMA": str(hub75_gamma),
        "HUB75_COLOR_ORDER": str(hub75_color_order),
        "HUB75_DEBUG_MODE": str(hub75_debug_mode),
        "MATRIX_ROTATE": str(rot),
        "MATRIX_FLIP_X": str(flip_x),
        "MATRIX_FLIP_Y": str(flip_y),
        "HUB75_BACKEND_VERSION": str(hub75_backend_ver),
        # WiFi / Web Update (optional)
        "WIFI_ENABLE": gv("wifi_enable", "0"),
        "WIFI_SSID": gv("wifi_ssid", ""),
        "WIFI_PASSWORD": gv("wifi_password", ""),
        "WIFI_HOSTNAME": gv("wifi_hostname", "modulo-hub75"),
        # WiFi AP fallback (optional captive portal for first-time setup)
        "WIFI_AP_FALLBACK": gv("wifi_ap_fallback", "0"),
        "WIFI_AP_PASSWORD": gv("wifi_ap_password", ""),
        # NTP time sync (optional)
        "WIFI_NTP_ENABLE": gv("wifi_ntp", "1"),
        "WIFI_TZ": gv("wifi_tz", "GMT0BST,M3.5.0/1,M10.5.0/2"),
        "WIFI_NTP1": gv("wifi_ntp1", "pool.ntp.org"),
        "WIFI_NTP2": gv("wifi_ntp2", "time.nist.gov"),
        # Dummy MSGEQ7 pins to satisfy template placeholders
        "MSGEQ7_RESET_PIN": str(meta.get("default_msgeq7_reset_pin", "16")),
        "MSGEQ7_STROBE_PIN": str(meta.get("default_msgeq7_strobe_pin", "17")),
        "MSGEQ7_LEFT_PIN": str(meta.get("default_msgeq7_left_pin", "34")),
        "MSGEQ7_RIGHT_PIN": str(meta.get("default_msgeq7_right_pin", "35")),
    }

    p = export_project_validated(
        ir.project,
        out_path,
        template_path=tpl,
        replacements=replacements,
    )

    report = (
        "Target: esp32_hub75_matrix_noneaudio\n"
        f"HUB75 backend: {hub75_backend_ver}\n"
        f"HUB75: panel={panel_x}x{panel_y} chain={chain} brightness={hub75_brightness} "
        f"color_order={hub75_color_order} debug_mode={hub75_debug_mode} "
        f"gamma={'on' if hub75_use_gamma else 'off'} ({hub75_gamma})\n"
        + (f"HUB75 infer: {inferred_note}\n" if inferred_note else "")
        + f"Cells: {mw}x{mh} rotate={rot} flip_x={flip_x} flip_y={flip_y}\n"
        + f"Written: {p}\n"
    )
    return (p, report)


# Exporters should consume SurfaceSpec via:
#   from app.project_model import get_surface_spec
from core.surface_compat import get_surface_mapping_values
#   spec = get_surface_spec(project)
# This prevents preview/export geometry divergence.

# ------------------------------------------------------------------
# All exporters must use SurfaceSpec for geometry truth
# ------------------------------------------------------------------
def _surface_geometry(project):
    spec = get_surface_spec(project)
    if not spec:
        raise RuntimeError("SurfaceSpec missing — export blocked.")
    mapping = get_surface_mapping_values(spec)
    return {
        "kind": spec.kind,
        "width": spec.width,
        "height": spec.height,
        "count": spec.count,
        "mapping": mapping,
        "serpentine": bool(mapping.get("serpentine", False)),
        "flip_x": bool(mapping.get("flip_x", False)),
        "flip_y": bool(mapping.get("flip_y", False)),
        "rotate": int(mapping.get("rotate", 0)),
        "origin": str(mapping.get("origin", "top_left")),
    }

# ------------------------------------------------------------------
# Legacy layout-based geometry access is deprecated.
# Exporters must NOT read project.surface.shape/width/height directly.
# Geometry authority = SurfaceSpec via get_surface_spec().
# ------------------------------------------------------------------
