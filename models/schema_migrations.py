from __future__ import annotations

from typing import Any, Dict

from .schema import CURRENT_SCHEMA_VERSION


def _migrate_schema_1_to_2(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 1 -> 2 migration:
    - Layers may have 'color', 'brightness', 'speed', etc at top-level (older builds).
    - Schema 2 stores these under layer['params'] dict.
    """
    layers = data.get("layers", []) or []
    new_layers = []
    for i, ld in enumerate(layers):
        if not isinstance(ld, dict):
            continue
        params = ld.get("params")
        if not isinstance(params, dict):
            params = {}
        # lift known keys into params if present
        for k in ("color","brightness","speed","width","softness","direction","density"):
            if k in ld and k not in params:
                params[k] = ld.get(k)
        # ensure required keys exist (defaults handled later)
        ld2 = dict(ld)
        ld2.pop("color", None)
        ld2.pop("brightness", None)
        ld2.pop("speed", None)
        ld2.pop("width", None)
        ld2.pop("softness", None)
        ld2.pop("direction", None)
        ld2.pop("density", None)
        ld2["params"] = params
        new_layers.append(ld2)
    data2 = dict(data)
    data2["layers"] = new_layers
    data2["schema_version"] = 2
    return data2

def _migrate_schema_2_to_3(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 2 -> 3 migration:
    - adds layer['blend_mode'] with default 'over' if missing
    """
    layers = data.get("layers", []) or []
    new_layers = []
    for ld in layers:
        if not isinstance(ld, dict):
            continue
        ld2 = dict(ld)
        if "blend_mode" not in ld2:
            ld2["blend_mode"] = "over"
        new_layers.append(ld2)
    data2 = dict(data)
    data2["layers"] = new_layers
    data2["schema_version"] = 3
    return data2

def _migrate_schema_3_to_4(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 3 -> 4 migration:
    - adds top-level groups/zones arrays if missing
    """
    data2 = dict(data)
    if "groups" not in data2 or not isinstance(data2.get("groups"), list):
        data2["groups"] = []
    if "zones" not in data2 or not isinstance(data2.get("zones"), list):
        data2["zones"] = []
    data2["schema_version"] = 4
    return data2

def _migrate_schema_4_to_5(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 4 -> 5 migration:
    - adds per-layer target_kind/target_ref (default all/0)
    """
    layers = data.get("layers", []) or []
    new_layers = []
    for ld in layers:
        if not isinstance(ld, dict):
            continue
        ld2 = dict(ld)
        if "target_kind" not in ld2:
            ld2["target_kind"] = "all"
        if "target_ref" not in ld2:
            ld2["target_ref"] = 0
        new_layers.append(ld2)
    data2 = dict(data)
    data2["layers"] = new_layers
    data2["schema_version"] = 5
    return data2

def _migrate_schema_5_to_6(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 5 -> 6 migration:
    - ensures per-modulotor 'bias' exists (default 0.0)
    """
    layers = data.get("layers", []) or []
    new_layers = []
    for ld in layers:
        if not isinstance(ld, dict):
            continue
        ld2 = dict(ld)
        mods = ld2.get("modulotors", []) or []
        new_mods = []
        for md in mods:
            if not isinstance(md, dict):
                new_mods.append(md)
                continue
            md2 = dict(md)
            if "bias" not in md2:
                md2["bias"] = 0.0
            new_mods.append(md2)
        ld2["modulotors"] = new_mods
        new_layers.append(ld2)
    data2 = dict(data)
    data2["layers"] = new_layers
    data2["schema_version"] = 6
    return data2

def _migrate_schema_6_to_7(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 6 -> 7 migration:
    - add matrix mapping defaults to layout (serpentine/flip/rotate)
    """
    d = dict(data)
    layout = dict(d.get("layout", {}) or {})
    layout.setdefault("serpentine", False)
    layout.setdefault("flip_x", False)
    layout.setdefault("flip_y", False)
    layout.setdefault("rotate", 0)
    d["layout"] = layout
    d["schema_version"] = 7
    return d

def _migrate_schema_7_to_8(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 7 -> 8 migration:
    - add layer.enabled default True
    """
    d = dict(data)
    layers = list(d.get("layers", []) or [])
    for L in layers:
        if isinstance(L, dict):
            L.setdefault("enabled", True)
    d["layers"] = layers
    d["schema_version"] = 8
    return d

def _migrate_schema_8_to_9(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 8 -> 9 migration:
    - add modulotor.enabled default True (per layer)
    """
    d = dict(data)
    layers = list(d.get("layers", []) or [])
    for L in layers:
        if isinstance(L, dict):
            mods = list(L.get("modulotors", []) or [])
            for m in mods:
                if isinstance(m, dict):
                    m.setdefault("enabled", True)
            L["modulotors"] = mods
    d["layers"] = layers
    d["schema_version"] = 9
    return d

def _migrate_schema_9_to_10(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 9 -> 10 migration:
    - modulotor.curve default 'linear'
    - modulotor.kind default 'audio'
    - for kind='lfo': add freq default 1.0, phase default 0.0
    """
    d = dict(data)
    layers = list(d.get("layers", []) or [])
    for L in layers:
        if isinstance(L, dict):
            mods = list(L.get("modulotors", []) or [])
            for m in mods:
                if isinstance(m, dict):
                    m.setdefault("curve", "linear")
                    m.setdefault("kind", "audio")
                    m.setdefault("freq", 1.0)
                    m.setdefault("phase", 0.0)
            L["modulotors"] = mods
    d["layers"] = layers
    d["schema_version"] = 10
    return d

def _migrate_schema_10_to_11(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 10 -> 11 migration:
    - add export_audio config with safe defaults
    """
    d = dict(data)
    d.setdefault("export_audio", {
        "use_spectrum_shield": True,
        "reset_pin": 5,
        "strobe_pin": 4,
        "left_pin": "A0",
        "right_pin": "A1",
    })
    d["schema_version"] = 11
    return d

def _migrate_schema_11_to_12(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 11 -> 12 migration:
    - add preview_audio config with safe defaults
    """
    d = dict(data)
    d.setdefault("preview_audio", {
        "mode": "sim",
        "port": "",
        "baud": 115200,
        "gain": 1.0,
        "smoothing": 0.20,
        "meter": "mono",
    })
    d["schema_version"] = 12
    return d

def _migrate_schema_12_to_13(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 12 -> 13 migration:
    - add preview_audio.autoconnect default False
    """
    d = dict(data)
    pa = dict(d.get("preview_audio") or {})
    pa.setdefault("autoconnect", False)
    d["preview_audio"] = pa
    d["schema_version"] = 13
    return d

def _migrate_schema_13_to_14(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 13 -> 14 migration:
    - add postfx config with safe defaults (disabled)
    - ensure export_audio and preview_audio exist (defensive for older files)
    """
    d = dict(data)
    d.setdefault("export_audio", {
        "use_spectrum_shield": True,
        "reset_pin": 5,
        "strobe_pin": 4,
        "left_pin": "A0",
        "right_pin": "A1",
    })
    d.setdefault("preview_audio", {
        "mode": "sim",
        "port": "",
        "baud": 115200,
        "gain": 1.0,
        "smoothing": 0.20,
        "meter": "mono",
        "autoconnect": False,
    })
    d.setdefault("postfx", {
        "bleed_amount": 0.0,
        "bleed_radius": 1,
        "trail_amount": 0.0,
    })
    d["schema_version"] = 14
    return d

def _migrate_schema_14_to_15(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 14 -> 15 migration:
    - add per-layer variables and rules arrays (default empty)
    """
    d = dict(data)
    layers = list(d.get("layers", []) or [])
    new_layers = []
    for L in layers:
        if not isinstance(L, dict):
            continue
        L2 = dict(L)
        if "variables" not in L2 or not isinstance(L2.get("variables"), list):
            L2["variables"] = []
        if "rules" not in L2 or not isinstance(L2.get("rules"), list):
            L2["rules"] = []
        new_layers.append(L2)
    d["layers"] = new_layers
    d["schema_version"] = 15
    return d

def _migrate_schema_15_to_16(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 15 -> 16 migration:
    - Canonicalize HUB75 export settings:
      If project.export.hub75 is missing but older UI keys exist (project.ui.export_hub75_*),
      copy them into project.export.hub75.*.

    This is intentionally best-effort and non-destructive:
    - It only writes keys that are missing in project.export.hub75
    - It leaves the UI keys intact for backwards compatibility
    """
    d = dict(data)
    ui = d.get("ui") if isinstance(d.get("ui"), dict) else {}
    export = d.get("export") if isinstance(d.get("export"), dict) else {}
    hub75 = export.get("hub75") if isinstance(export.get("hub75"), dict) else {}

    # If export.hub75 already exists with something in it, we still top-up missing fields.
    # If there are no UI keys, do nothing.
    ui_map = {
        "panel_res_x": "export_hub75_panel_res_x",
        "panel_res_y": "export_hub75_panel_res_y",
        "panel_preset": "export_hub75_panel_preset",
        "chain": "export_hub75_chain",
        "num_cols": "export_hub75_num_cols",
        "num_rows": "export_hub75_num_rows",
        "virtual_chain_type": "export_hub75_virtual_chain_type",
        "brightness": "export_hub75_brightness",
        "use_gamma": "export_hub75_use_gamma",
        "gamma": "export_hub75_gamma",
        "color_order": "export_hub75_color_order",
        "debug_mode": "export_hub75_debug_mode",
        "wifi_enable": "export_hub75_wifi_enable",
        "wifi_ssid": "export_hub75_wifi_ssid",
        "wifi_password": "export_hub75_wifi_password",
        "wifi_hostname": "export_hub75_wifi_hostname",
        "wifi_ap_fallback": "export_hub75_wifi_ap_fallback",
        "wifi_ap_password": "export_hub75_wifi_ap_password",
    }

    changed = False
    for k_exp, k_ui in ui_map.items():
        if k_exp in hub75:
            continue
        if k_ui in ui:
            hub75[k_exp] = ui.get(k_ui)
            changed = True

    if changed:
        export2 = dict(export)
        export2["hub75"] = hub75
        d["export"] = export2

    d["schema_version"] = 16
    return d

def _migrate_schema_16_to_17(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 16 -> 17 migration:
    - canonicalize HUB75 settings fully into project.export.hub75
    - remove legacy project.ui.export_hub75_* keys after migration

    Legacy UI keys are migration-only and must not survive as a second source of truth.
    """
    d = dict(data)
    ui = d.get("ui") if isinstance(d.get("ui"), dict) else {}
    ui2 = dict(ui)
    export = d.get("export") if isinstance(d.get("export"), dict) else {}
    hub75 = export.get("hub75") if isinstance(export.get("hub75"), dict) else {}

    ui_map = {
        "panel_res_x": "export_hub75_panel_res_x",
        "panel_res_y": "export_hub75_panel_res_y",
        "panel_preset": "export_hub75_panel_preset",
        "chain": "export_hub75_chain",
        "num_cols": "export_hub75_num_cols",
        "num_rows": "export_hub75_num_rows",
        "virtual_chain_type": "export_hub75_virtual_chain_type",
        "brightness": "export_hub75_brightness",
        "use_gamma": "export_hub75_use_gamma",
        "gamma": "export_hub75_gamma",
        "color_order": "export_hub75_color_order",
        "debug_mode": "export_hub75_debug_mode",
        "wifi_enable": "export_hub75_wifi_enable",
        "wifi_ssid": "export_hub75_wifi_ssid",
        "wifi_password": "export_hub75_wifi_password",
        "wifi_hostname": "export_hub75_wifi_hostname",
        "wifi_ap_fallback": "export_hub75_wifi_ap_fallback",
        "wifi_ap_password": "export_hub75_wifi_ap_password",
    }

    changed = False
    removed = False
    for k_exp, k_ui in ui_map.items():
        if k_exp not in hub75 and k_ui in ui2:
            hub75[k_exp] = ui2.get(k_ui)
            changed = True
        if k_ui in ui2:
            ui2.pop(k_ui, None)
            removed = True

    if changed:
        export2 = dict(export)
        export2["hub75"] = hub75
        d["export"] = export2
    if removed or "ui" in d:
        d["ui"] = ui2

    d["schema_version"] = 17
    return d


def _migrate_schema_17_to_18(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 17 -> 18 migration:
    - migrate legacy project.ui export selection keys into canonical export.*
    - migrate legacy project.ui hardware keys into canonical export.hw.*
    - migrate legacy project.ui MSGEQ7 keys into canonical export.audio_hw.*
    - remove migrated legacy UI export keys so runtime stays single-path
    """
    d = dict(data)
    ui = d.get("ui") if isinstance(d.get("ui"), dict) else {}
    ui2 = dict(ui)
    export = d.get("export") if isinstance(d.get("export"), dict) else {}
    export2 = dict(export)

    changed = False
    removed = False

    sel_map = {
        "led_backend": "export_led_backend",
        "audio_backend": "export_audio_backend",
    }
    for k_exp, k_ui in sel_map.items():
        if not str(export2.get(k_exp) or "").strip() and str(ui2.get(k_ui) or "").strip():
            export2[k_exp] = ui2.get(k_ui)
            changed = True
        if k_ui in ui2:
            ui2.pop(k_ui, None)
            removed = True

    hw = export2.get("hw") if isinstance(export2.get("hw"), dict) else {}
    hw = dict(hw)
    hw_map = {
        "data_pin": "export_data_pin",
        "led_type": "export_led_type",
        "color_order": "export_color_order",
        "brightness": "export_brightness",
    }
    for k_exp, k_ui in hw_map.items():
        if hw.get(k_exp) is None or str(hw.get(k_exp) or "").strip() == "":
            if str(ui2.get(k_ui) or "").strip():
                hw[k_exp] = ui2.get(k_ui)
                changed = True
        if k_ui in ui2:
            ui2.pop(k_ui, None)
            removed = True
    if hw:
        export2["hw"] = hw

    audio_hw = export2.get("audio_hw") if isinstance(export2.get("audio_hw"), dict) else {}
    audio_hw = dict(audio_hw)
    aud_map = {
        "msgeq7_reset_pin": "export_msgeq7_reset_pin",
        "msgeq7_strobe_pin": "export_msgeq7_strobe_pin",
        "msgeq7_left_pin": "export_msgeq7_left_pin",
        "msgeq7_right_pin": "export_msgeq7_right_pin",
    }
    for k_exp, k_ui in aud_map.items():
        if audio_hw.get(k_exp) is None or str(audio_hw.get(k_exp) or "").strip() == "":
            if str(ui2.get(k_ui) or "").strip():
                audio_hw[k_exp] = ui2.get(k_ui)
                changed = True
        if k_ui in ui2:
            ui2.pop(k_ui, None)
            removed = True
    if audio_hw:
        export2["audio_hw"] = audio_hw

    if changed:
        d["export"] = export2
    if removed or "ui" in d:
        d["ui"] = ui2

    d["schema_version"] = 18
    return d




def _migrate_schema_18_to_19(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 18 -> 19 migration:
    - migrate legacy project.export.hardware into canonical project.export.hw
    - preserve existing export.hw as authoritative when both exist
    - remove legacy export.hardware after migration so export resolution stays single-path
    """
    d = dict(data)
    export = d.get("export") if isinstance(d.get("export"), dict) else {}
    export2 = dict(export)
    hw = export2.get("hw") if isinstance(export2.get("hw"), dict) else {}
    hw = dict(hw)
    legacy_hw = export2.get("hardware") if isinstance(export2.get("hardware"), dict) else {}
    legacy_hw = dict(legacy_hw)

    changed = False
    if legacy_hw:
        for k, v in legacy_hw.items():
            if k not in hw or hw.get(k) in (None, ""):
                hw[k] = v
                changed = True
        export2["hw"] = hw
    if "hardware" in export2:
        export2.pop("hardware", None)
        changed = True

    if changed:
        d["export"] = export2
    d["schema_version"] = 19
    return d



def _migrate_schema_19_to_20(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 19 -> 20 migration:
    - collapse legacy per-layer effect shadow into canonical layer.behavior
    - merge legacy effect params into layer.params when present
    - remove layer.effect after migration so layer identity stays single-path
    """
    d = dict(data)
    layers = list(d.get("layers", []) or [])
    new_layers = []
    for ld in layers:
        if not isinstance(ld, dict):
            new_layers.append(ld)
            continue
        ld2 = dict(ld)
        params = ld2.get("params") if isinstance(ld2.get("params"), dict) else {}
        params = dict(params)
        effect_obj = ld2.get("effect")
        effect_id = ""
        if isinstance(effect_obj, dict):
            effect_id = str(effect_obj.get("id") or effect_obj.get("key") or "").strip()
            eff_params = effect_obj.get("params")
            if isinstance(eff_params, dict):
                merged = dict(eff_params)
                merged.update(params)
                params = merged
        else:
            effect_id = str(effect_obj or "").strip()
        if (ld2.get("behavior") is None or str(ld2.get("behavior") or "").strip() == "") and effect_id:
            ld2["behavior"] = effect_id
        ld2["params"] = params
        ld2.pop("effect", None)
        new_layers.append(ld2)
    d["layers"] = new_layers
    d["schema_version"] = 20
    return d


def _migrate_schema_20_to_21(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 20 -> 21 migration:
    - canonicalize layout shape/count semantics into layout.shape/width/height/count
    - migrate legacy layout.type='matrix' into canonical layout.shape='cells'
    - migrate legacy count aliases (num_leds/led_count) into canonical layout.count
    - remove legacy layout aliases after migration so layout stays single-path
    """
    d = dict(data)
    layout = d.get("layout") if isinstance(d.get("layout"), dict) else {}
    layout2 = dict(layout)

    shape = str(layout2.get("shape") or layout2.get("type") or "").strip().lower()
    if shape in ("matrix", "grid"):
        shape = "cells"
    elif shape in ("line", ""):
        shape = "strip" if not (int(layout2.get("width") or layout2.get("w") or 0) > 0 and int(layout2.get("height") or layout2.get("h") or 0) > 0) else "cells"

    width = int(layout2.get("width") or layout2.get("w") or layout2.get("matrix_w") or layout2.get("mw") or 0)
    height = int(layout2.get("height") or layout2.get("h") or layout2.get("matrix_h") or layout2.get("mh") or 0)
    count = int(layout2.get("count") or layout2.get("num_leds") or layout2.get("led_count") or 0)

    if shape == "cells":
        layout2["shape"] = "cells"
        if width > 0:
            layout2["width"] = width
        if height > 0:
            layout2["height"] = height
        if width > 0 and height > 0:
            layout2["count"] = width * height
        elif count > 0:
            layout2["count"] = count
    else:
        layout2["shape"] = "strip"
        if count <= 0 and width > 0 and height <= 1:
            count = width
        if count > 0:
            layout2["count"] = count

    for k in ("type", "w", "h", "mw", "mh", "matrix_w", "matrix_h", "num_leds", "led_count"):
        layout2.pop(k, None)

    d["layout"] = layout2
    d["schema_version"] = 21
    return d

def migrate_to_current(data: Dict[str, Any]) -> Dict[str, Any]:
    v = int(data.get("schema_version", 1))
    # Chain migrations in order
    if v == 1 and CURRENT_SCHEMA_VERSION >= 2:
        data = _migrate_schema_1_to_2(data)
        v = 2
    if v == 2 and CURRENT_SCHEMA_VERSION >= 3:
        data = _migrate_schema_2_to_3(data)
        v = 3
    if v == 3 and CURRENT_SCHEMA_VERSION >= 4:
        data = _migrate_schema_3_to_4(data)
        v = 4
    if v == 4 and CURRENT_SCHEMA_VERSION >= 5:
        data = _migrate_schema_4_to_5(data)
        v = 5
    if v == 5 and CURRENT_SCHEMA_VERSION >= 6:
        data = _migrate_schema_5_to_6(data)
        v = 6
    if v == 6 and CURRENT_SCHEMA_VERSION >= 7:
        data = _migrate_schema_6_to_7(data)
        v = 7
    if v == 7 and CURRENT_SCHEMA_VERSION >= 8:
        data = _migrate_schema_7_to_8(data)
        v = 8
    if v == 8 and CURRENT_SCHEMA_VERSION >= 9:
        data = _migrate_schema_8_to_9(data)
        v = 9
    if v == 9 and CURRENT_SCHEMA_VERSION >= 10:
        data = _migrate_schema_9_to_10(data)
        v = 10
    if v == 10 and CURRENT_SCHEMA_VERSION >= 11:
        data = _migrate_schema_10_to_11(data)
        v = 11
    if v == 11 and CURRENT_SCHEMA_VERSION >= 12:
        data = _migrate_schema_11_to_12(data)
        v = 12
    if v == 12 and CURRENT_SCHEMA_VERSION >= 13:
        data = _migrate_schema_12_to_13(data)
        v = 13
    if v == 13 and CURRENT_SCHEMA_VERSION >= 14:
        data = _migrate_schema_13_to_14(data)
        v = 14
    if v == 14 and CURRENT_SCHEMA_VERSION >= 15:
        data = _migrate_schema_14_to_15(data)
        v = 15
    if v == 15 and CURRENT_SCHEMA_VERSION >= 16:
        data = _migrate_schema_15_to_16(data)
        v = 16
    if v == 16 and CURRENT_SCHEMA_VERSION >= 17:
        data = _migrate_schema_16_to_17(data)
        v = 17
    if v == 17 and CURRENT_SCHEMA_VERSION >= 18:
        data = _migrate_schema_17_to_18(data)
        v = 18
    if v == 18 and CURRENT_SCHEMA_VERSION >= 19:
        data = _migrate_schema_18_to_19(data)
        v = 19
    if v == 19 and CURRENT_SCHEMA_VERSION >= 20:
        data = _migrate_schema_19_to_20(data)
        v = 20
    if v == 20 and CURRENT_SCHEMA_VERSION >= 21:
        data = _migrate_schema_20_to_21(data)
        v = 21
    # If unknown newer version, we still try to load best-effort
    return data

