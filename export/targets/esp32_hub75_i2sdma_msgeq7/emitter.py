from __future__ import annotations

from pathlib import Path
from typing import Tuple
import json

from ...ir import ShowIR
from ...arduino_exporter import export_project_validated, HUB75_LED_IMPL_ESP32
from ..registry import resolve_requested_backends, resolve_requested_hw, resolve_requested_audio_hw


def _get_meta() -> dict:
    try:
        return json.loads((Path(__file__).resolve().parent / "target.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def emit(*, ir: ShowIR, out_path: Path, **_kwargs) -> Tuple[Path, str]:
    """ESP32 HUB75 (I2S-DMA) matrix target pack (MSGEQ7 audio)."""
    tpl = Path(__file__).resolve().parent / "arduino_template.ino.tpl"
    meta = _get_meta()

    sel = resolve_requested_backends(ir.project, meta)
    hw = resolve_requested_hw(ir.project, meta)
    aud = resolve_requested_audio_hw(ir.project, meta, sel.get('audio_backend'))

    # This pack is intended for MSGEQ7; any other selected audio backend disables it.
    use_msgeq7 = 1 if str(sel.get('audio_backend') or '').strip().lower() in ('msgeq7', 'msgeq7_stereo', 'spectrum_shield', 'spectrum') else 0

    # HUB75 config: prefer canonical project.export.hub75.*, fallback to meta defaults.
    exp = (ir.project or {}).get('export') or {}
    hub = exp.get('hub75') or {}
    if not isinstance(hub, dict):
        hub = {}

    defs = ((meta.get('capabilities') or {}).get('defaults') or {})

    def gv(key: str, default: str) -> str:
        v = hub.get(key)
        if v is None:
            v = defs.get(f'hub75_{key}', default)
        return str(v)

    replacements = {
        'USE_MSGEQ7': str(use_msgeq7),
        'LED_IMPL': HUB75_LED_IMPL_ESP32,

        # HUB75 tokens
        'HUB75_PANEL_RES_X': gv('panel_res_x', '64'),
        'HUB75_PANEL_RES_Y': gv('panel_res_y', '32'),
        'HUB75_CHAIN': gv('chain', '1'),
        'HUB75_NUM_ROWS': gv('num_rows', '1'),
        'HUB75_NUM_COLS': gv('num_cols', '1'),
        'HUB75_VIRTUAL_CHAIN_TYPE': gv('virtual_chain_type', 'CHAIN_TOP_LEFT_DOWN'),
        'HUB75_BRIGHTNESS': gv('brightness', '96'),
        'HUB75_USE_GAMMA': gv('use_gamma', '0'),
        'HUB75_GAMMA': gv('gamma', '2.2f'),
        'HUB75_COLOR_ORDER': gv('color_order', '0'),
        'HUB75_DEBUG_MODE': gv('debug_mode', '0'),
        'HUB75_DOUBLE_BUFFER': gv('double_buffer', '1'),
        'HUB75_PINSET': gv('pinset', '0'),
        'HUB75_BACKEND_VERSION': meta.get('hub75_backend_version', 'v0.1'),
        # WiFi / Web Update (optional)
        'WIFI_ENABLE': gv('wifi_enable', '0'),
        'WIFI_SSID': gv('wifi_ssid', ''),
        'WIFI_PASSWORD': gv('wifi_password', ''),
        'WIFI_HOSTNAME': gv('wifi_hostname', 'modulo-hub75'),

        # WiFi AP fallback (optional captive portal for first-time setup)
        'WIFI_AP_FALLBACK': gv('wifi_ap_fallback', '0'),
        'WIFI_AP_PASSWORD': gv('wifi_ap_password', ''),

        # NTP time sync (optional)
        'WIFI_NTP_ENABLE': gv('wifi_ntp', '1'),
        'WIFI_TZ': gv('wifi_tz', 'GMT0BST,M3.5.0/1,M10.5.0/2'),
        'WIFI_NTP1': gv('wifi_ntp1', 'pool.ntp.org'),
        'WIFI_NTP2': gv('wifi_ntp2', 'time.nist.gov'),


        # Keep these around for templates expecting them; unused for HUB75.
        'DATA_PIN': str(hw.get('data_pin', '23')),
        'LED_TYPE': str(hw.get('led_type', 'WS2812B')),
        'COLOR_ORDER': str(hw.get('color_order', 'GRB')),
        'LED_BRIGHTNESS': str(hw.get('brightness', '96')),

        # MSGEQ7 pins
        'MSGEQ7_RESET_PIN': str(aud.get('msgeq7_reset_pin', meta.get('default_msgeq7_reset_pin', '5'))),
        'MSGEQ7_STROBE_PIN': str(aud.get('msgeq7_strobe_pin', meta.get('default_msgeq7_strobe_pin', '4'))),
        'MSGEQ7_LEFT_PIN': str(aud.get('msgeq7_left_pin', meta.get('default_msgeq7_left_pin', 'A0'))),
        'MSGEQ7_RIGHT_PIN': str(aud.get('msgeq7_right_pin', meta.get('default_msgeq7_right_pin', 'A1'))),
    }

    p = export_project_validated(
        ir.project,
        out_path,
        template_path=tpl,
        replacements=replacements,
    )

    report = (
        f"Target: {meta.get('id', 'esp32_hub75_i2sdma_msgeq7')}\n"
        f"Written: {p}\n"
        f"HUB75 backend: {meta.get('hub75_backend_version','v0.1')}\n"
        f"Audio backend: {sel.get('audio_backend')} (USE_MSGEQ7={use_msgeq7})\n"
    )
    return Path(p), report