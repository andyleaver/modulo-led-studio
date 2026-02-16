from __future__ import annotations

"""Target capability profiles (MVP)

This module normalizes target.meta into a stable 'capabilities' dict used by parity checks and reports.

Design goal:
- one exporter engine
- multiple targets differentiated by capability profiles and emit backends
"""

from typing import Any, Dict, List


DEFAULT_CAPS: Dict[str, Any] = {
    # basic
    "supports_platformio": True,
    "supports_arduino_ino": True,

    # layouts
    "supports_strip": True,
    "supports_matrix": False,

    # LED backends / libraries
    "led_backends": ["fastled"],  # allowed: fastled, neopixel

    # audio backends
    "audio_backends": ["none", "msgeq7_sim", "msgeq7"],

    # limits (None = unknown)
    "ram_limit_bytes": None,
    "flash_limit_bytes": None,
    "max_leds_recommended": None,
    "max_leds_hard": None,
}


REQUIRED_CAPS_V1 = {
    'supports_arduino_ino': False,
    'supports_platformio': False,
    'supports_strip': True,
    'supports_matrix': False,
    'led_backends': ['FastLED'],
    'audio_backends': ['none'],
    'ram_limit_bytes': None,
    'flash_limit_bytes': None,
    'max_leds_recommended': None,
    'max_leds_hard': None,
    'allowed_led_types': None,
    'allowed_data_pins': None,
    'allowed_color_orders': None,
    'allowed_color_orders_by_led_backend': None,
    'allowed_led_types_by_led_backend': None,
    'provides_defaults': None,
    'default_keys': None,
    'allowed_msgeq7_adc_pins': None,
    'recommended_data_pins': None,
    'allowed_msgeq7_reset_pins': None,
    'allowed_msgeq7_strobe_pins': None,
    'allowed_msgeq7_left_pins': None,
    'allowed_msgeq7_right_pins': None,
    'brightness_min': None,
    'brightness_max': None,
    'allowed_matrix_origins': None,
    'supports_matrix_serpentine': None,
    # runtime subsystems (fail-closed)
    'supports_operators_runtime': False,
    'supports_postfx_runtime': False,
    'supports_rules_runtime': False,
    'supports_modulotion_runtime': False,
    'max_matrix_width': None,
    'max_matrix_height': None,
}


def normalize_capabilities(meta: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return a normalized capabilities dict.

    Accepts either:
      - meta['capabilities'] dict
      - legacy meta fields (ram_limit_bytes, max_leds_*, etc.)

    Always returns a dict with DEFAULT_CAPS keys.
    """
    meta = dict(meta or {})
    caps = dict(DEFAULT_CAPS)

    raw = meta.get("capabilities")
    if isinstance(raw, dict):
        caps.update({k: raw.get(k) for k in raw.keys()})

    # legacy/meta fallbacks
    for k in ("ram_limit_bytes","flash_limit_bytes","max_leds_recommended","max_leds_hard"):
        if meta.get(k) is not None:
            caps[k] = meta.get(k)

    # normalize lists
    if not isinstance(caps.get("led_backends"), list):
        caps["led_backends"] = list(DEFAULT_CAPS["led_backends"])
    if not isinstance(caps.get("audio_backends"), list):
        caps["audio_backends"] = list(DEFAULT_CAPS["audio_backends"])

    # ensure strings + lower
    caps["led_backends"] = [str(x).lower() for x in caps["led_backends"] if str(x).strip()]
    caps["audio_backends"] = [str(x).lower() for x in caps["audio_backends"] if str(x).strip()]

    # booleans
    for b in ("supports_platformio","supports_arduino_ino","supports_strip","supports_matrix"):
        caps[b] = bool(caps.get(b))

    # Ensure required v1 keys exist
    for k,v in REQUIRED_CAPS_V1.items():
        if k not in caps:
            caps[k] = v
    return caps


def caps_supports_layout(caps: Dict[str, Any], layout_kind: str) -> bool:
    k = str(layout_kind or "").lower()
    if k == "strip":
        return bool(caps.get("supports_strip", True))
    if k == "matrix":
        return bool(caps.get("supports_matrix", False))
    return False


def caps_supports_led_backend(caps: Dict[str, Any], led_backend: str) -> bool:
    lb = str(led_backend or "").lower()
    return lb in set(caps.get("led_backends") or [])


def caps_supports_audio_backend(caps: Dict[str, Any], audio_backend: str) -> bool:
    ab = str(audio_backend or "").lower()
    return ab in set(caps.get("audio_backends") or [])
