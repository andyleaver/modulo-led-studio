from __future__ import annotations

import sys
import uuid
from pathlib import Path

from app.app_identity import get_app_id as _get_app_id
from app.project_canonical import apply_project_root

APP_TITLE = "Modulo LED Studio"
APP_ID = _get_app_id(Path(__file__).resolve().parents[1])

BETA_DETERMINISTIC_SIGNAL_SET = [
    "time_ms",
    "frame",
    "dt_ms",
    "audio_energy",
    "audio_peak",
    "audio_mono_band_0..6",
    "audio_left_band_0..6",
    "audio_right_band_0..6",
]

BETA_TARGET_CAPABILITIES = {
    "preview": {
        "operators_runtime": False,
        "modulotors": False,
        "audio": True,
        "stateful_effects": True,
    },
    "arduino": {
        "operators_runtime": False,
        "modulotors": False,
        "audio": True,
        "stateful_effects": False,
    },
}

_DEBUG_PALETTE = [
    (230, 57, 70),
    (241, 250, 238),
    (29, 53, 87),
    (69, 123, 157),
    (42, 157, 143),
    (233, 196, 106),
    (244, 162, 97),
    (231, 111, 81),
    (155, 93, 229),
    (0, 180, 216),
    (144, 190, 109),
]


def install_global_excepthook(app_name: str = "Modulo"):
    """Show a fatal error dialog instead of silently closing on uncaught exceptions."""
    try:
        from qt.qt_compat import QtWidgets  # type: ignore
    except Exception:
        QtWidgets = None  # type: ignore

    def _hook(exctype, value, tb):
        try:
            import traceback as _tb
            msg = "".join(_tb.format_exception(exctype, value, tb))
        except Exception:
            msg = f"{exctype.__name__}: {value}"
        try:
            sys.stderr.write(msg + "\n")
        except Exception:
            pass
        try:
            if QtWidgets is not None and QtWidgets.QApplication.instance() is not None:
                QtWidgets.QMessageBox.critical(None, f"{app_name} — Fatal Error", "An unexpected error occurred.\n\n" + msg[-4000:])
        except Exception:
            pass

    sys.excepthook = _hook


def pick_debug_color(index: int) -> tuple[int, int, int]:
    try:
        return _DEBUG_PALETTE[int(index) % len(_DEBUG_PALETTE)]
    except Exception:
        return (200, 200, 200)


def ensure_zone_ids_and_debug(project_dict: dict) -> dict:
    zones = list(project_dict.get("zones") or [])
    changed = False
    normalized = []
    for index, zone in enumerate(zones):
        if not isinstance(zone, dict):
            continue
        zone_copy = dict(zone)
        if not zone_copy.get("id"):
            zone_copy["id"] = uuid.uuid4().hex
            changed = True
        if not zone_copy.get("debug_color"):
            zone_copy["debug_color"] = list(pick_debug_color(index))
            changed = True
        normalized.append(zone_copy)
    if changed:
        project_copy, _validation, _changes = apply_project_root(project_dict, "zones", normalized)
        return project_copy
    return project_dict


def ensure_layer_debug(project_dict: dict) -> dict:
    layers = list(project_dict.get("layers") or [])
    changed = False
    normalized = []
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict):
            continue
        layer_copy = dict(layer)
        if not layer_copy.get("id"):
            layer_copy["id"] = uuid.uuid4().hex
            changed = True
        if not layer_copy.get("debug_color"):
            layer_copy["debug_color"] = list(pick_debug_color(index))
            changed = True
        normalized.append(layer_copy)
    if changed:
        project_copy, _validation, _changes = apply_project_root(project_dict, "layers", normalized)
        return project_copy
    return project_dict


def normalize_project_for_editor(project_dict: dict) -> dict:
    return ensure_layer_debug(ensure_zone_ids_and_debug(project_dict))


def make_hline(QtWidgets):
    frame = QtWidgets.QFrame()
    try:
        frame.setFrameShape(QtWidgets.QFrame.Shape.HLine)
    except Exception:
        frame.setFrameShape(QtWidgets.QFrame.HLine)  # type: ignore
    try:
        frame.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
    except Exception:
        try:
            frame.setFrameShadow(QtWidgets.QFrame.Sunken)  # type: ignore
        except Exception:
            pass
    return frame
