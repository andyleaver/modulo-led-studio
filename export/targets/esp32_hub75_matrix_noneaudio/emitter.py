from __future__ import annotations

from pathlib import Path
from typing import Tuple
import json

from ...ir import ShowIR
from ...arduino_exporter import export_project_validated, HUB75_LED_IMPL_ESP32
from ..registry import resolve_requested_hw

def emit(*, ir: ShowIR, out_path: Path, **_kwargs) -> Tuple[Path, str]:
    """ESP32 HUB75 (I2S-DMA) target pack (matrix-only, no-audio)."""
    tpl = Path(__file__).resolve().parent / "arduino_template.ino.tpl"

    meta = {}
    try:
        meta = json.loads((Path(__file__).resolve().parent / "target.json").read_text(encoding="utf-8"))
    except Exception:
        meta = {}

    hw = resolve_requested_hw(ir.project, meta)

    # Hub75 geometry (panel res + chain)
    # Prefer project.export.hub75.*, then UI export_hub75_* keys, then target defaults.
    proj = ir.project or {}
    exp = (proj.get("export") or {}).get("hub75") or {}
    ui = (proj.get("ui") or {})

    panel_x = int(exp.get("panel_res_x") or ui.get("export_hub75_panel_res_x") or meta.get("default_hub75_panel_res_x", 64))
    panel_y = int(exp.get("panel_res_y") or ui.get("export_hub75_panel_res_y") or meta.get("default_hub75_panel_res_y", 32))
    chain   = int(exp.get("chain")      or ui.get("export_hub75_chain")       or meta.get("default_hub75_chain", 1))

    # Brightness + gamma output options
    hub75_brightness = int(exp.get("brightness") or ui.get("export_hub75_brightness") or meta.get("default_hub75_brightness", hw.get("brightness", 96)))
    hub75_use_gamma  = int(exp.get("use_gamma")  or ui.get("export_hub75_use_gamma") or meta.get("default_hub75_use_gamma", 0))
    hub75_gamma      = exp.get("gamma") or ui.get("export_hub75_gamma") or meta.get("default_hub75_gamma", "2.2f")

    # Optional HUB75 output tweaks
    hub75_color_order = int(exp.get("color_order") or ui.get("export_hub75_color_order") or meta.get("default_hub75_color_order", 0))
    hub75_debug_mode  = int(exp.get("debug_mode")  or ui.get("export_hub75_debug_mode")  or meta.get("default_hub75_debug_mode", 0))
    hub75_backend_ver = str(meta.get("hub75_backend_version") or "v0.1")

    # Fail-closed: this target expects matrix/cells layout with matching dimensions.
    # We keep it strict so users don't burn time compiling mismatched exports.
    shape = str((proj.get("layout") or {}).get("kind") or "").lower().strip()
    if shape not in ("cells", "matrix"):
        return (out_path, "BLOCKED: HUB75 target requires a matrix/cells layout.")

    hwmat = (proj.get("export") or {}).get("hw") or {}
    m = (hwmat.get("matrix") or {})
    mw = int(m.get("width") or 0)
    mh = int(m.get("height") or 0)

    rot = int(m.get('rotate') or 0)
    flip_x = int(m.get('flip_x') or 0)
    flip_y = int(m.get('flip_y') or 0)
    # Auto-infer HUB75 geometry when possible (helps first-time exports).
    inferred = []
    if panel_x <= 0:
        panel_x = int(meta.get('default_hub75_panel_res_x', 64)) or 64
    if panel_y <= 0:
        panel_y = int(meta.get('default_hub75_panel_res_y', 32)) or 32
    if chain <= 0:
        chain = 1
    # If MATRIX dims are known, try to infer chain if it doesn't match.
    if mw > 0 and panel_x > 0:
        if mw != panel_x * chain and (mw % panel_x) == 0:
            new_chain = mw // panel_x
            if new_chain > 0:
                inferred.append(f'chain {chain}->' + str(new_chain))
                chain = int(new_chain)
    # If MATRIX height matches multiple panels vertically, warn (this pack is horizontal-chain only).
    if mh > 0 and panel_y > 0 and mh != panel_y:
        if (mh % panel_y) == 0:
            inferred.append('vertical_panels=' + str(mh // panel_y) + ' (not supported)')
    inferred_note = ('; '.join(inferred)) if inferred else ''

    if mw <= 0 or mh <= 0:
        return (out_path, "BLOCKED: HUB75 target requires export.hw.matrix.width/height to be set.")

    if mw != panel_x * chain:
        return (out_path, f"BLOCKED: MATRIX_WIDTH ({mw}) must equal panel_res_x*chain ({panel_x}*{chain}={panel_x*chain}).")
    if mh != panel_y:
        return (out_path, f"BLOCKED: MATRIX_HEIGHT ({mh}) must equal panel_res_y ({panel_y}). Vertical chaining not enabled in this pack.")

    p = export_project_validated(
        ir.project,
        out_path,
        template_path=tpl,
        replacements={
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
        'WIFI_NTP_ENABLE': gv('wifi_ntp', '1'),
        'WIFI_TZ': gv('wifi_tz', 'GMT0BST,M3.5.0/1,M10.5.0/2'),
        'WIFI_NTP1': gv('wifi_ntp1', 'pool.ntp.org'),
        'WIFI_NTP2': gv('wifi_ntp2', 'time.nist.gov'),
            # Dummy MSGEQ7 pins to satisfy template placeholders
            "MSGEQ7_RESET_PIN": str(meta.get("default_msgeq7_reset_pin", "16")),
            "MSGEQ7_STROBE_PIN": str(meta.get("default_msgeq7_strobe_pin", "17")),
            "MSGEQ7_LEFT_PIN": str(meta.get("default_msgeq7_left_pin", "34")),
            "MSGEQ7_RIGHT_PIN": str(meta.get("default_msgeq7_right_pin", "35")),
        },
    )

    report = (
        "Target: esp32_hub75_matrix_noneaudio\n"
        f"HUB75 backend: {hub75_backend_ver}\n"
        f"HUB75: panel={panel_x}x{panel_y} chain={chain} brightness={hub75_brightness} "
        f"color_order={hub75_color_order} debug_mode={hub75_debug_mode} "
        f"gamma={'on' if hub75_use_gamma else 'off'} ({hub75_gamma})\n"
        + (f"HUB75 infer: {inferred_note}\n" if inferred_note else "")
        + f"Matrix: {mw}x{mh} rotate={rot} flip_x={flip_x} flip_y={flip_y}\n"
        + f"Written: {p}\n"
    )
    return (p, report)