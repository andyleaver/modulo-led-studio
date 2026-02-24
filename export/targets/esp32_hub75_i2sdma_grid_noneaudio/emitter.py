from __future__ import annotations

from pathlib import Path
from typing import Tuple
import json

from ...ir import ShowIR
from ...arduino_exporter import export_project_validated, HUB75_LED_IMPL_ESP32
from ..registry import resolve_requested_hw


def _get_meta() -> dict:
    try:
        return json.loads((Path(__file__).resolve().parent / "target.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def emit(*, ir: ShowIR, out_path: Path, **_kwargs) -> Tuple[Path, str]:
    """ESP32 HUB75 (I2S-DMA) matrix GRID target pack (no-audio)."""
    tpl = Path(__file__).resolve().parent / "arduino_template.ino.tpl"
    meta = _get_meta()

    exp = (ir.project or {}).get("export") or {}
    hub = exp.get("hub75") or {}
    if not isinstance(hub, dict):
        hub = {}

    defs = ((meta.get("capabilities") or {}).get("defaults") or {})

    def gv(key: str, default: str) -> str:
        v = hub.get(key)
        if v is None:
            v = defs.get(f"hub75_{key}", default)
        return str(v)

    # Matrix dims (resolved by export_project_validated): require MATRIX_WIDTH/HEIGHT to exist for HUB75.
    hw = resolve_requested_hw(ir.project, meta)

    # Resolve grid geometry
    panel_x = int(float(gv("panel_res_x", "64")))
    panel_y = int(float(gv("panel_res_y", "32")))
    num_rows = int(float(gv("num_rows", "1")))
    num_cols = int(float(gv("num_cols", "1")))
    if num_rows < 1: num_rows = 1
    if num_cols < 1: num_cols = 1

    panel_chain = num_rows * num_cols

    # Virtual chain type: allow either numeric or CHAIN_* symbolic names
    vchain_raw = gv("virtual_chain_type", "CHAIN_TOP_LEFT_DOWN").strip()
    vchain_map = {
        "CHAIN_TOP_LEFT_DOWN": "CHAIN_TOP_LEFT_DOWN",
        "CHAIN_TOP_RIGHT_DOWN": "CHAIN_TOP_RIGHT_DOWN",
        "CHAIN_BOTTOM_LEFT_UP": "CHAIN_BOTTOM_LEFT_UP",
        "CHAIN_BOTTOM_RIGHT_UP": "CHAIN_BOTTOM_RIGHT_UP",
        "0": "CHAIN_TOP_LEFT_DOWN",
        "1": "CHAIN_TOP_RIGHT_DOWN",
        "2": "CHAIN_BOTTOM_LEFT_UP",
        "3": "CHAIN_BOTTOM_RIGHT_UP",
    }
    vchain = vchain_map.get(vchain_raw, vchain_raw)

    # Strict dimension checks (fail-closed)
    # We read matrix dims from project export.hw.matrix if present, else layout dims.
    mat = (exp.get("hw") or {}).get("matrix") or {}
    mw = mat.get("width")
    mh = mat.get("height")
    # fallback to layout dims
    if not mw or not mh:
        lay = (ir.project or {}).get("layout") or {}
        mw = mw or lay.get("width")
        mh = mh or lay.get("height")

    def _as_int(x):
        try:
            return int(float(x))
        except Exception:
            return 0

    mw = _as_int(mw)
    mh = _as_int(mh)

    expected_w = panel_x * num_cols
    expected_h = panel_y * num_rows

    blocked_reason = None
    kind = ((ir.project or {}).get("layout") or {}).get("kind")
    if kind not in ("matrix", "cells"):
        blocked_reason = f"HUB75 grid export requires layout.kind matrix/cells (got {kind!r})."
    elif mw <= 0 or mh <= 0:
        blocked_reason = "HUB75 grid export requires matrix width/height to be set."
    elif mw != expected_w or mh != expected_h:
        blocked_reason = (
            f"HUB75 grid dims mismatch: matrix={mw}x{mh}, expected={expected_w}x{expected_h} "
            f"(panel={panel_x}x{panel_y}, cols={num_cols}, rows={num_rows})."
        )

    if blocked_reason:
        # Match existing UX: raise a ValueError so export report marks as blocked.
        raise ValueError(blocked_reason)

    replacements = {
        "USE_MSGEQ7": "0",
        "LED_IMPL": HUB75_LED_IMPL_ESP32,

        # HUB75 tokens
        "HUB75_PANEL_RES_X": str(panel_x),
        "HUB75_PANEL_RES_Y": str(panel_y),
        "HUB75_CHAIN": str(panel_chain),
        "HUB75_NUM_ROWS": str(num_rows),
        "HUB75_NUM_COLS": str(num_cols),
        "HUB75_VIRTUAL_CHAIN_TYPE": str(vchain),
        "HUB75_BRIGHTNESS": gv("brightness", "96"),
        "HUB75_USE_GAMMA": gv("use_gamma", "0"),
        "HUB75_GAMMA": gv("gamma", "2.2f"),
        "HUB75_COLOR_ORDER": gv("color_order", "0"),
        "HUB75_DEBUG_MODE": gv("debug_mode", "0"),
        "HUB75_DOUBLE_BUFFER": gv("double_buffer", "1"),
        "HUB75_PINSET": gv("pinset", "0"),
        "HUB75_BACKEND_VERSION": meta.get("hub75_backend_version","v0.1"),

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

        # Keep these around for templates expecting them; unused for HUB75.
        "DATA_PIN": str(hw.get("data_pin", "23")),
        "LED_TYPE": str(hw.get("led_type", "WS2812B")),
        "COLOR_ORDER": str(hw.get("color_order", "GRB")),
        "LED_BRIGHTNESS": str(hw.get("brightness", "96")),
    }

    p = export_project_validated(
        ir.project,
        out_path,
        template_path=tpl,
        replacements=replacements,
    )

    report = (
        f"Target: {meta.get('id','esp32_hub75_i2sdma_grid_noneaudio')}\n"
        f"Written: {p}\n"
        f"HUB75 backend: {meta.get('hub75_backend_version','v0.1')}\n"
        f"HUB75 grid: panel={panel_x}x{panel_y} cols={num_cols} rows={num_rows} chain={panel_chain} vchain={vchain_raw}\n"
    )
    return Path(p), report