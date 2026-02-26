from __future__ import annotations
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any

from .types import TargetSpec
from .capabilities import normalize_capabilities

# Built-in targets live alongside this file: export/targets/<id>/
_BUILTIN_DIR = Path(__file__).resolve().parent

# Project root (…/export/targets/registry.py -> …/export/targets -> …/export -> <root>)
_APP_ROOT = _BUILTIN_DIR.parents[2]

# Optional user targets directory (safe place for users to drop their own target packs)
# Layout: user_targets/export_targets/<target_pack>/{target.json, emitter.py, templates…}
_USER_DIR_DEFAULT = _APP_ROOT / "user_targets" / "export_targets"

# Optional additional search paths via env var (semicolon separated on Windows, colon on *nix)
_ENV_PATHS = os.environ.get("MODULA_EXPORT_TARGETS_PATH", "")

_REQUIRED_KEYS = {"id", "name", "emitter_module"}
# Release: Supported targets v1 (others are experimental).
# This is a truth/UX contract, not a feature gate: experimental targets remain selectable.
SUPPORTED_TARGET_IDS_V1 = {
    "arduino_uno_fastled_msgeq7",
    "arduino_uno_pio_fastled_msgeq7",
    "arduino_mega_fastled_msgeq7",
    "arduino_mega_pio_fastled_msgeq7",
    "esp32_fastled_msgeq7",
    "rp2040_fastled_noneaudio",
}



def resolve_requested_backends(project: dict, target_meta: dict) -> dict:
    """Resolve requested led_backend/audio_backend with strict precedence.

    Precedence:
      1) project.export.led_backend / project.export.audio_backend (explicit)
      2) legacy project.ui.export_led_backend / project.ui.export_audio_backend (if present)
      3) target defaults (target_meta.capabilities.defaults)
      4) final fallback: led_backend="fastled", audio_backend="none"

    Returned dict always contains: led_backend, audio_backend
    """
    project = project or {}
    exp = project.get("export") or {}
    ui = project.get("ui") or {}

    def _norm(v: object) -> str:
        s = str(v).strip()
        return s.lower()

    # target defaults (optional)
    defaults = {}
    try:
        defaults = ((target_meta or {}).get("capabilities") or {}).get("defaults") or {}
        if not isinstance(defaults, dict):
            defaults = {}
    except Exception:
        defaults = {}

    # explicit export config wins
    led_backend = exp.get("led_backend")
    audio_backend = exp.get("audio_backend")

    # legacy UI fallbacks only if explicit missing
    if not str(led_backend or "").strip() and isinstance(ui, dict):
        led_backend = ui.get("export_led_backend")
    if not str(audio_backend or "").strip() and isinstance(ui, dict):
        audio_backend = ui.get("export_audio_backend")

    # target defaults only if still missing
    if not str(led_backend or "").strip():
        led_backend = defaults.get("led_backend")
    if not str(audio_backend or "").strip():
        audio_backend = defaults.get("audio_backend")

    # final fallbacks (fail-closed semantics elsewhere)
    led_backend = _norm(led_backend) if str(led_backend or "").strip() else "fastled"
    audio_backend = _norm(audio_backend) if str(audio_backend or "").strip() else "none"

    return {"led_backend": led_backend, "audio_backend": audio_backend}
def resolve_requested_hw(project: Dict[str, Any], target_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve requested wiring defaults (data pin, LED type, color order, brightness).

    Stored under project['ui']:
      - export_data_pin (string; may be numeric or board-specific like 'A0')
      - export_led_type (FastLED chipset token, e.g. WS2812B)
      - export_color_order (FastLED color order token, e.g. GRB)
      - export_brightness (0..255)

    Target packs may declare:
      - led_types, color_orders (allowed lists)
      - default_data_pin, default_led_type, default_color_order, default_brightness
    """
    ui = project.get('ui') or {}
    req_pin = str(ui.get('export_data_pin') or '').strip()
    req_type = str(ui.get('export_led_type') or '').strip()
    req_order = str(ui.get('export_color_order') or '').strip()
    req_bright = str(ui.get('export_brightness') or '').strip()


    export_cfg = project.get('export') or {}
    export_hw = export_cfg.get('hw') or export_cfg.get('hardware') or {}
    if isinstance(export_hw, dict):
        # prefer explicit export.hw values
        req_pin = str(export_hw.get('data_pin') or req_pin).strip()
        req_type = str(export_hw.get('led_type') or req_type).strip()
        req_order = str(export_hw.get('color_order') or req_order).strip()
        req_bright = str(export_hw.get('brightness') or req_bright).strip()



    led_types = list(target_meta.get('led_types') or [])
    color_orders = list(target_meta.get('color_orders') or [])

    def_pin = str((target_meta.get('defaults') or {}).get('data_pin') or target_meta.get('default_data_pin') or '6')
    def_type = str((target_meta.get('defaults') or {}).get('led_type') or target_meta.get('default_led_type') or (led_types[0] if led_types else 'WS2812B'))
    def_order = str((target_meta.get('defaults') or {}).get('color_order') or target_meta.get('default_color_order') or (color_orders[0] if color_orders else 'GRB'))
    def_bright = str((target_meta.get('defaults') or {}).get('brightness') or target_meta.get('default_brightness') or '255')

    notes: List[str] = []

    pin = req_pin or def_pin
    led_type = req_type or def_type
    order = req_order or def_order
    bright = req_bright or def_bright

    if led_types and led_type not in led_types:
        notes.append(f"Requested LED type '{led_type}' not supported by target; using '{def_type}'.")
        led_type = def_type
    if color_orders and order not in color_orders:
        notes.append(f"Requested color order '{order}' not supported by target; using '{def_order}'.")
        order = def_order

    # Brightness normalization
    try:
        b = int(float(bright))
    except Exception:
        b = int(float(def_bright)) if str(def_bright).strip() else 255
    if b < 0:
        b = 0
    if b > 255:
        b = 255
    bright = str(b)

    hw = {
        'data_pin': pin,
        'led_type': led_type,
        'color_order': order,
        'brightness': bright,
        'notes': notes,
    }
    # Propagate matrix hardware request if provided (used for matrix layout exports/reporting).
    export_cfg = project.get("export") or {}
    export_hw = export_cfg.get("hw") or export_cfg.get("hardware") or {}
    if isinstance(export_hw, dict):
        m = export_hw.get("matrix")
        if isinstance(m, dict) and m:
            hw["matrix"] = m
    return hw


def resolve_requested_audio_hw(project: Dict[str, Any], target_meta: Dict[str, Any], audio_backend: str | None = None) -> Dict[str, Any]:
    """Resolve audio wiring defaults for the selected audio backend.

    Currently supports MSGEQ7/Spectrum Shield pins.
    Stored under project['ui']:
      - export_msgeq7_reset_pin
      - export_msgeq7_strobe_pin
      - export_msgeq7_left_pin
      - export_msgeq7_right_pin

    Target packs may declare defaults:
      - default_msgeq7_reset_pin, default_msgeq7_strobe_pin, default_msgeq7_left_pin, default_msgeq7_right_pin
    """
    ui = project.get('ui') or {}
    ab = (audio_backend or ui.get('export_audio_backend') or 'none')
    ab_l = str(ab).strip().lower()

    # Only meaningful for msgeq7-like backends.
    if ab_l not in ('msgeq7','spectrum_shield','spectrum','shield'):
        return {'use_msgeq7': 0, 'notes': []}

    notes: List[str] = []
    def_reset = str((target_meta.get('defaults') or {}).get('msgeq7_reset_pin') or target_meta.get('default_msgeq7_reset_pin') or '5')
    def_strobe = str((target_meta.get('defaults') or {}).get('msgeq7_strobe_pin') or target_meta.get('default_msgeq7_strobe_pin') or '4')
    def_left = str((target_meta.get('defaults') or {}).get('msgeq7_left_pin') or target_meta.get('default_msgeq7_left_pin') or 'A0')
    def_right = str((target_meta.get('defaults') or {}).get('msgeq7_right_pin') or target_meta.get('default_msgeq7_right_pin') or 'A1')

    reset = str(ui.get('export_msgeq7_reset_pin') or '').strip() or def_reset
    strobe = str(ui.get('export_msgeq7_strobe_pin') or '').strip() or def_strobe
    left = str(ui.get('export_msgeq7_left_pin') or '').strip() or def_left
    right = str(ui.get('export_msgeq7_right_pin') or '').strip() or def_right

    # Normalize numeric pins if possible (leave A0-style as-is)
    def _norm_pin(v: str, fallback: str) -> str:
        vv = str(v).strip()
        if not vv:
            return fallback
        if re.fullmatch(r"-?\d+", vv):
            try:
                return str(int(vv))
            except Exception:
                return fallback
        return vv

    reset_n = _norm_pin(reset, def_reset)
    strobe_n = _norm_pin(strobe, def_strobe)
    left_n = _norm_pin(left, def_left)
    right_n = _norm_pin(right, def_right)

    return {
        'use_msgeq7': 1,
        'msgeq7_reset_pin': reset_n,
        'msgeq7_strobe_pin': strobe_n,
        'msgeq7_left_pin': left_n,
        'msgeq7_right_pin': right_n,
        'notes': notes,
    }

def _iter_search_dirs() -> List[Path]:
    dirs: List[Path] = [_BUILTIN_DIR]
    if _USER_DIR_DEFAULT.exists():
        dirs.append(_USER_DIR_DEFAULT)

    # Extra dirs from env var
    if _ENV_PATHS.strip():
        sep = ";" if os.name == "nt" else ":"
        for raw in _ENV_PATHS.split(sep):
            p = Path(raw.strip()).expanduser()
            if p.exists() and p.is_dir():
                dirs.append(p)
    # De-dup while preserving order
    out: List[Path] = []
    seen = set()
    for d in dirs:
        if d not in seen:
            out.append(d)
            seen.add(d)
    return out


def diagnose_target_packs() -> Dict[str, Any]:
    """Return diagnostic info about all discovered target packs (built-in + user).

    Unlike list_targets(), this does NOT swallow malformed packs; it returns them as errors.
    Used by health probes and CI gates.
    """
    ok: List[dict] = []
    errors: List[dict] = []
    from .validate_target_pack import validate_target_pack
    for d in _discover_target_dirs():
        d = Path(d)
        try:
            meta = _read_meta(d)
        except Exception as e:
            errors.append({
                "dir": str(d),
                "error": f"failed to read target.json: {type(e).__name__}: {e}",
            })
            continue
        valid, verrs = validate_target_pack(meta)
        if not valid:
            errors.append({
                "dir": str(d),
                "id": meta.get("id"),
                "name": meta.get("name"),
                "errors": verrs,
            })
            continue
        try:
            meta['capabilities'] = normalize_capabilities(meta)
        except Exception as e:
            errors.append({
                "dir": str(d),
                "id": meta.get("id"),
                "name": meta.get("name"),
                "error": f"capabilities normalize failed: {type(e).__name__}: {e}",
            })
            continue
        meta = _hoist_caps_legacy_fields(meta)
        tid = str(meta.get('id') or '')
        meta['support_level'] = 'supported' if tid in SUPPORTED_TARGET_IDS_V1 else 'experimental'
        meta['source'] = 'builtin' if str(d).startswith(str(_BUILTIN_DIR)) else 'user'
        ok.append(meta)
    ok.sort(key=lambda m: (m.get("name","").lower(), m.get("id","")))
    return {"ok": ok, "errors": errors, "supported_v1": sorted(SUPPORTED_TARGET_IDS_V1)}
def _discover_target_dirs() -> List[Path]:
    found: List[Path] = []
    for base in _iter_search_dirs():
        for p in base.iterdir():
            if p.is_dir() and (p / "target.json").exists():
                found.append(p)
    return sorted(found)

def _read_meta(target_dir: Path) -> Dict[str, Any]:
    meta_path = target_dir / "target.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"Invalid target.json in {target_dir}: {e}") from e

    missing = [k for k in sorted(_REQUIRED_KEYS) if k not in meta]
    if missing:
        raise RuntimeError(f"Target pack '{target_dir.name}' is missing required keys in target.json: {missing}")

    # Helpful derived fields
    meta.setdefault("source_dir", str(target_dir))
    meta.setdefault("source", "user" if str(target_dir).startswith(str(_USER_DIR_DEFAULT)) else "builtin")
    return meta

def _hoist_caps_legacy_fields(meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Back-compat helper: move legacy root-level capability keys under meta["capabilities"].
    """
    if not isinstance(meta, dict):
        return meta
    caps = meta.get("capabilities")
    if not isinstance(caps, dict):
        caps = {}
        meta["capabilities"] = caps

    legacy_keys = [
        "max_led_count",
        "recommended_led_count",
        "supports_matrix_layout",
        "allowed_led_backends",
        "allowed_audio_backends",
        "allowed_msgeq7_adc_pins",
        "recommended_data_pins",
        "allowed_matrix_origins",
        "supports_serpentine",
        "defaults",
        "placeholder",
    ]
    for k in legacy_keys:
        if k in meta and k not in caps:
            caps[k] = meta.get(k)
    return meta

def list_targets() -> List[dict]:
    out: List[dict] = []
    for d in _discover_target_dirs():
        try:
            meta = _read_meta(d)
            try:
                meta['capabilities'] = normalize_capabilities(meta)
            except Exception:
                pass
            meta = _hoist_caps_legacy_fields(meta)
            try:
                tid = str(meta.get('id') or '')
                meta['support_level'] = 'supported' if tid in SUPPORTED_TARGET_IDS_V1 else 'experimental'
            except Exception:
                meta['support_level'] = 'experimental'
            out.append(meta)
        except Exception:
            # Don't crash the UI if a user target is malformed; it will show up as an error at export time
            continue
    # Sort by name for nicer UI
    out.sort(key=lambda m: (m.get("name","").lower(), m.get("id","")))
    return out

def load_target(target_id: str) -> TargetSpec:
    # Back-compat aliases (legacy fixture/UX ids)
    tid = (target_id or '').strip()
    if tid.startswith('platformio_uno_'):
        tid = tid.replace('platformio_uno_', 'arduino_uno_pio_', 1)
    if tid.startswith('platformio_mega_'):
        tid = tid.replace('platformio_mega_', 'arduino_mega_pio_', 1)
    target_id = tid

    for d in _discover_target_dirs():
        meta = _read_meta(d)
        if meta.get("id") == target_id:
            emitter_path = meta.get("emitter_module", "")
            if not emitter_path:
                raise RuntimeError(f"Target '{target_id}' missing emitter_module in target.json")

            mod = __import__(emitter_path, fromlist=["emit"])
            emit_fn = getattr(mod, "emit", None)
            if not callable(emit_fn):
                raise RuntimeError(f"Target '{target_id}' emitter_module '{emitter_path}' does not expose a callable emit(ir, out_dir)")

            return TargetSpec(
                id=meta.get("id", target_id),
                name=meta.get("name", target_id),
                meta=meta,
                emit=emit_fn,
            )
    raise KeyError(f"Unknown export target: {target_id}")


def get_user_targets_dir() -> Path:
    """Return the directory where user target packs should be placed (created if missing)."""
    p = _USER_DIR_DEFAULT
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return p

def validate_targets() -> List[Dict[str, str]]:
    """Validate all discovered target packs.

    Returns a list of problem dicts:
      {"id": <pack id>, "path": <pack path>, "error": <message>}
    An empty list means all packs look valid.
    """
    problems: List[Dict[str, str]] = []
    for d in _discover_target_dirs():
        try:
            meta = _read_meta(d)  # validates required keys + JSON
            # Try import of emitter module so errors show before export
            emitter_path = str(meta.get("emitter_module") or "").strip()
            if emitter_path:
                mod = __import__(emitter_path, fromlist=["emit"])
                emit_fn = getattr(mod, "emit", None)
                if not callable(emit_fn):
                    raise RuntimeError("emitter_module does not expose a callable 'emit'")
        except Exception as e:
            problems.append({
                "id": d.name,
                "path": str(d),
                "error": str(e),
            })
    return problems

def create_sample_target_pack(pack_id: str | None = None) -> Path:
    """Create a minimal sample target pack in the user targets directory and return its path."""
    base = get_user_targets_dir()
    # Choose a unique id/folder name
    if not pack_id:
        stamp = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
        pack_id = f"sample_board_{stamp}"
    safe = ''.join(ch if (ch.isalnum() or ch in ('_', '-')) else '_' for ch in pack_id)
    out_dir = base / safe
    n = 1
    while out_dir.exists():
        out_dir = base / f"{safe}_{n}"
        n += 1
    out_dir.mkdir(parents=True, exist_ok=True)

    # Ensure Python package markers exist for dynamic import
    (base / '__init__.py').write_text('# user_targets package\n', encoding='utf-8')
    (base.parent / '__init__.py').write_text('# user_targets root package\n', encoding='utf-8')

    # Minimal target.json + emitter.py
    (out_dir / "target.json").write_text(json.dumps({
        "id": out_dir.name,
        "name": f"User Sample ({out_dir.name})",
        "arch": "generic",
        "description": "Sample user target pack (FastLED, no audio). Edit target.json + emitter.py to customize.",
        "source": "user",
        "emitter_module": f"user_targets.export_targets.{out_dir.name}.emitter",
        "led_backends": ["FastLED"],
        "audio_backends": ["none"],
        "default_led_backend": "FastLED",
        "default_audio_backend": "none",
        "ram_limit_bytes": 128000,
        "max_leds_recommended": 300,
        "default_fps": 60,
    }, indent=2), encoding="utf-8")

    # NOTE: Use triple single quotes for this embedded Python source so it can
    # safely contain an f"""...""" C++ block without terminating this string.
    (out_dir / "emitter.py").write_text('''# User target pack emitter (sample)
# This emitter is intentionally tiny: it delegates to Modulo's legacy Arduino exporter.

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from export.ir import ShowIR
from export.arduino_exporter import export_project_validated


def emit(*, ir: ShowIR, out_path: Path) -> Tuple[Path, str]:
    """Sample emit() compatible with Modulo's target interface."""
    # If you want a custom template, add one to this folder and pass template_path=...
    ino_path = export_project_validated(ir.project, out_path)
    report = "Target: user_sample\n" + f"Written: {ino_path}\n"
    return Path(ino_path), report
''', encoding="utf-8")

    # Python package marker so emitter_module import works (nested packages)
    # Ensure user_targets/export_targets is a package too if user extracts next to app
    return out_dir
