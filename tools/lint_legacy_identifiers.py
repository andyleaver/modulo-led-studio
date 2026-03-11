#!/usr/bin/env python3
from __future__ import annotations
"""
lint_legacy_identifiers.py

Fail the build if deprecated schema identifiers are referenced outside of approved migration/probe code.

This is stricter than lint_legacy_schema: it blocks *code* from reading/writing old keys, ensuring
legacy stays import-only (handled in normalization).

It intentionally allows migration/diagnostic surfaces, but runtime/preview/export code must stay
on canonical keys only.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEPRECATED_QUOTED_KEYS = [
    "mw", "mh",
    "matrix_w", "matrix_h",
    "num_leds",
    "led_count",
    "led_pin",
    "matrix_serpentine", "matrix_flip_x", "matrix_flip_y", "matrix_rotate",
    "export_hub75_panel_res_x", "export_hub75_panel_res_y", "export_hub75_panel_preset",
    "export_hub75_chain", "export_hub75_num_cols", "export_hub75_num_rows",
    "export_hub75_virtual_chain_type", "export_hub75_brightness", "export_hub75_use_gamma",
    "export_hub75_gamma", "export_hub75_color_order", "export_hub75_debug_mode",
    "export_hub75_wifi_enable", "export_hub75_wifi_ssid", "export_hub75_wifi_password",
    "export_hub75_wifi_hostname", "export_hub75_wifi_ap_fallback", "export_hub75_wifi_ap_password",
    "export_led_backend", "export_audio_backend",
    "export_data_pin", "export_led_type", "export_color_order", "export_brightness",
    "export_msgeq7_reset_pin", "export_msgeq7_strobe_pin", "export_msgeq7_left_pin", "export_msgeq7_right_pin",
]

KEY_RE = re.compile(
    r"""(?x)
    (?:\.\s*get\s*\(\s*['"](?P<k1>[a-zA-Z0-9_]+)['"]\s*\)) |
    (?:\[\s*['"](?P<k2>[a-zA-Z0-9_]+)['"]\s*\])
    """
)

ALLOWLIST = {
    "app/project_manager_layout.py",
    "models/schema_migrations.py",
    "app/project_normalize_state.py",
    "app/project_manager_layers_state.py",
    "qt/diagnostics_console_audit_core.py",
    "tools/lint_legacy_schema.py",
    "tools/lint_legacy_identifiers.py",
    "behaviors/effects/_export_hw.py",
}

LEGACY_EFFECT_KEY_RE = re.compile(r"(?x)(?:\.\s*get\s*\(\s*['\"]effect['\"]\s*\))|(?:\[\s*['\"]effect['\"]\s*\])")
LEGACY_BLEND_NORMAL_RE = re.compile(r'''["']blend_mode["']\s*:\s*["']normal["']''')


def main() -> int:
    problems = []
    for path in ROOT.rglob("*.py"):
        rel = str(path.relative_to(ROOT))
        if rel in ALLOWLIST:
            continue
        txt = path.read_text(encoding="utf-8", errors="ignore")

        if any(k in txt for k in DEPRECATED_QUOTED_KEYS):
            for m in KEY_RE.finditer(txt):
                k = m.group("k1") or m.group("k2")
                if k in DEPRECATED_QUOTED_KEYS:
                    line_no = txt.count("\n", 0, m.start()) + 1
                    problems.append(f"{rel}:{line_no}: deprecated key reference '{k}'")

        for m in LEGACY_EFFECT_KEY_RE.finditer(txt):
            line_no = txt.count("\n", 0, m.start()) + 1
            problems.append(f"{rel}:{line_no}: legacy layer identity reference 'effect'")

        for m in LEGACY_BLEND_NORMAL_RE.finditer(txt):
            line_no = txt.count("\n", 0, m.start()) + 1
            problems.append(f"{rel}:{line_no}: canonical composition fixture uses legacy blend_mode 'normal'")

    if problems:
        print("ERROR: deprecated schema identifiers referenced outside migration/probe code.")
        for p in problems:
            print(" -", p)
        return 2
    print("OK: no deprecated schema identifiers referenced outside migration/probe code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
