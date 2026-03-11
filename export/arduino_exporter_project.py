from __future__ import annotations

from pathlib import Path

from app.project_model import get_surface_spec, get_surface_snapshot
from core.surface_compat import get_surface_mapping_values, normalize_surface_mapping
from app.project_canonical import canonicalize_project_dict
from export.preconditions import check as _check_preconditions
from export.export_eligibility import get_eligibility, ExportStatus
from export.arduino_exporter_validation import ExportValidationError, export_sketch, _load_target_hooks, _inject_target_hooks


def export_project_layerstack_impl(*, project: dict, template_path, out_path, replacements: dict | None, make_layerstack_sketch_fn, fastled_led_impl: str, matrix_impl: str):
    project, _canon_changes = canonicalize_project_dict(project or {})
    code = make_layerstack_sketch_fn(project=project)
    hooks = _load_target_hooks(Path(template_path) if template_path is not None else None)
    code = _inject_target_hooks(code, hooks)
    rep = dict(replacements or {})
    layers_list = list((project or {}).get('layers') or [])
    rep.setdefault('LAYER_COUNT', str(len(layers_list)))
    if 'GROUP_INDEXES_LEN' not in rep:
        gi = rep.get('GROUP_INDEXES')
        if isinstance(gi, str):
            s = gi.strip()
            if s.startswith('{') and s.endswith('}'):
                inner = s[1:-1].strip()
                rep['GROUP_INDEXES_LEN'] = '0' if not inner else str(len([p for p in inner.split(',') if p.strip()]))
        rep.setdefault('GROUP_INDEXES_LEN', '0')
    rep.setdefault('LED_IMPL', fastled_led_impl)
    rep.setdefault('MATRIX_IMPL', '')
    try:
        spec = get_surface_spec(project)
        kind = str(getattr(spec, 'kind', '') or '').strip().lower()
        if kind == 'cells':
            rep['MATRIX_IMPL'] = matrix_impl
    except Exception:
        rep['MATRIX_IMPL'] = ''
    return export_sketch(sketch_code=code, template_path=template_path, out_path=out_path, replacements=rep)


def validate_project_layout_compat_impl(project: dict) -> None:
    project, _canon_changes = canonicalize_project_dict(project or {})
    layout_kind = None
    try:
        spec = get_surface_spec(project)
        k = str(getattr(spec, 'kind', '')).strip().lower() if spec is not None else ''
        if k in ('strip',):
            layout_kind = 'strip'
        elif k == 'cells':
            layout_kind = 'cells'
    except Exception:
        layout_kind = None
    if layout_kind not in ('strip', 'cells'):
        return
    from behaviors.registry import load_capabilities_catalog
    caps = load_capabilities_catalog().get('effects', {}) or {}
    bad = []
    for i, layer in enumerate(project.get('layers') or []):
        try:
            key = str(layer.get('behavior') or '').strip()
        except Exception:
            key = ''
        if not key:
            continue
        supports = str((caps.get(key) or {}).get('supports', 'both'))
        if layout_kind == 'strip' and supports not in ('strip', 'both'):
            bad.append((i, key, supports))
        if layout_kind == 'cells' and supports not in ('cells', 'both'):
            bad.append((i, key, supports))
    if bad:
        msg = f"Layout incompatibility: project is {layout_kind} but these layers are not supported:\n"
        for i, key, supports in bad[:20]:
            msg += f"  layer[{i}] behavior='{key}' supports={supports}\n"
        if len(bad) > 20:
            msg += f"  ...and {len(bad)-20} more\n"
        msg += 'Fix: change layout OR remove/replace those layers.'
        raise ExportValidationError(msg)


def export_project_validated_impl(project: dict, out_path: Path, *, template_path: Path | None, replacements: dict | None, export_project_layerstack_fn, fastled_led_impl: str) -> Path:
    project, _canon_changes = canonicalize_project_dict(project or {})
    res = _check_preconditions(project or {})
    if isinstance(res, tuple) and len(res) == 3:
        ok, problems, _warns = res
    else:
        ok, problems = res
    if not ok:
        msg = 'Export preconditions failed:\n'
        for p in (problems or []):
            msg += f'- {p}\n'
        raise ExportValidationError(msg.strip())
    validate_project_layout_compat_impl(project)
    try:
        for li, layer in enumerate((project or {}).get('layers') or []):
            if not isinstance(layer, dict):
                continue
            beh = str(layer.get('behavior') or '').strip()
            if not beh:
                continue
            elig = get_eligibility(beh)
            if getattr(elig, 'status', '') != ExportStatus.EXPORTABLE:
                reason = getattr(elig, 'reason', '') or 'Not exportable'
                raise ExportValidationError(f"[E_BEHAVIOR_NOT_EXPORTABLE] layer {li} behavior '{beh}' is {elig.status}: {reason}")
    except ExportValidationError:
        raise
    except Exception:
        pass
    # Canonical export must not synthesize export.hw.matrix from layout at runtime.
    # Geometry truth comes from SurfaceSpec and MATRIX_* replacements below.
    tpl = template_path or (Path(__file__).resolve().parents[1] / 'export' / 'arduino_template.ino.tpl')
    if replacements is None:
        replacements = {}
    replacements.setdefault('LED_IMPL', fastled_led_impl)
    replacements.setdefault('WIFI_ENABLE', '0')
    replacements.setdefault('WIFI_SSID', '')
    replacements.setdefault('WIFI_PASSWORD', '')
    replacements.setdefault('WIFI_HOSTNAME', 'modulo')
    replacements.setdefault('WIFI_NTP_ENABLE', '1')
    replacements.setdefault('WIFI_TZ', 'GMT0BST,M3.5.0/1,M10.5.0/2')
    replacements.setdefault('WIFI_NTP1', 'pool.ntp.org')
    replacements.setdefault('WIFI_NTP2', 'time.nist.gov')
    exp = (project or {}).get('export') or {}
    explicit_ab = str(exp.get('audio_backend') or '').strip().lower()
    if explicit_ab == 'none':
        replacements.setdefault('USE_MSGEQ7', '0')
    elif explicit_ab == 'msgeq7':
        replacements.setdefault('USE_MSGEQ7', '1')
    else:
        replacements.setdefault('USE_MSGEQ7', '1')
    replacements.setdefault('MSGEQ7_RESET_PIN', '5')
    replacements.setdefault('MSGEQ7_STROBE_PIN', '4')
    replacements.setdefault('MSGEQ7_LEFT_PIN', 'A0')
    replacements.setdefault('MSGEQ7_RIGHT_PIN', 'A1')
    try:
        spec = get_surface_spec(project)
    except Exception:
        spec = None
    try:
        if spec is not None and getattr(spec, 'kind', None):
            kind = str(spec.kind).strip().lower()
            mapping = getattr(spec, 'mapping', None) or {}
            if kind == 'cells':
                mw = int(getattr(spec, 'width', 0) or 0)
                mh = int(getattr(spec, 'height', 0) or 0)
                if mw > 0 and mh > 0:
                    replacements.setdefault('MATRIX_WIDTH', str(mw))
                    replacements.setdefault('MATRIX_HEIGHT', str(mh))
                mapping = get_surface_mapping_values(spec, fallback={"mapping": mapping})
                serp = mapping.get('serpentine', False)
                origin = mapping.get('origin', 'top_left')
                rot = mapping.get('rotate', 0)
                fx = 1 if mapping.get('flip_x', False) else 0
                fy = 1 if mapping.get('flip_y', False) else 0
                replacements.setdefault('MATRIX_SERPENTINE', '1' if serp else '0')
                replacements.setdefault('MATRIX_ORIGIN', origin)
                replacements.setdefault('MATRIX_ROTATE', str(rot))
                replacements.setdefault('MATRIX_FLIP_X', str(fx))
                replacements.setdefault('MATRIX_FLIP_Y', str(fy))
    except Exception:
        pass
    hw = exp.get('hw') or {}
    data_pin = str((hw or {}).get('data_pin') or '').strip()
    if not data_pin:
        data_pin = str(replacements.get('DATA_PIN') or '').strip() or '6'
    replacements.setdefault('DATA_PIN', data_pin)
    replacements.setdefault('LED_TYPE', str((hw or {}).get('led_type') or '').strip() or 'WS2812B')
    replacements.setdefault('COLOR_ORDER', str((hw or {}).get('color_order') or '').strip() or 'GRB')
    b = (hw or {}).get('brightness', '')
    try:
        bv = int(float(str(b).strip()))
    except Exception:
        bv = 255
    replacements.setdefault('LED_BRIGHTNESS', str(max(0, min(255, bv))))
    return export_project_layerstack_fn(project=project, template_path=tpl, out_path=out_path, replacements=replacements)


def export_project_impl(*, project: dict, out_path: Path, template_path: Path | None, export_project_validated_fn):
    p = export_project_validated_fn(project, out_path, template_path=template_path)
    report = f"Target: arduino_avr_fastled_msgeq7\nWritten: {p}\n"
    return Path(p), report
