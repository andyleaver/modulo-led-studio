from __future__ import annotations

from typing import Dict, Any, List, Tuple

REQUIRED_BOOL = ("supports_arduino_ino","supports_platformio","supports_strip","supports_matrix")
REQUIRED_LIST = ("led_backends","audio_backends")
REQUIRED_LIMITS = ("ram_limit_bytes","flash_limit_bytes","max_leds_recommended","max_leds_hard")
OPTIONAL_LIST_OR_NULL = (
    "allowed_led_types","allowed_data_pins","allowed_color_orders",
    "allowed_msgeq7_reset_pins","allowed_msgeq7_strobe_pins",
    "allowed_msgeq7_left_pins","allowed_msgeq7_right_pins",
    "allowed_matrix_origins",
)

def validate_capabilities(caps: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(caps, dict):
        return False, ["capabilities is not a dict"]

    for k in REQUIRED_BOOL:
        if k not in caps or not isinstance(caps.get(k), bool):
            errors.append(f"capabilities.{k} missing or not bool")

    for k in REQUIRED_LIST:
        v = caps.get(k)
        if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
            errors.append(f"capabilities.{k} missing or not list[str]")

    for k in REQUIRED_LIMITS:
        v = caps.get(k)
        if v is not None and not isinstance(v, int):
            errors.append(f"capabilities.{k} must be int or null")

    for k in OPTIONAL_LIST_OR_NULL:
        vv = caps.get(k)
        if vv is not None:
            if not isinstance(vv, list) or not all(isinstance(x, (str,int)) for x in vv):
                errors.append(f"capabilities.{k} must be list[str|int] or null")


    vvv = caps.get("supports_matrix_serpentine")
    if vvv is not None and (not isinstance(vvv, bool)):
        errors.append("capabilities.supports_matrix_serpentine must be bool or null")

    for k in ("brightness_min","brightness_max","max_matrix_width","max_matrix_height"):
        vv = caps.get(k)
        if vv is not None and (not isinstance(vv, int)):
            errors.append(f"capabilities.{k} must be int or null")

    return (len(errors) == 0), errors
