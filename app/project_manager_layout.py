from __future__ import annotations

from app.project_apply import replace_project_root
from app.project_manager_diagnostics import project_manager_diag_exc
from app.project_model import build_surface_from_evidence, coerce_surface_kind, get_raw_surface_evidence
from core.surface_compat import canonicalize_surface_geometry, get_surface_kind_value, normalize_surface_kind, normalize_surface_mapping
_pm_diag_exc = project_manager_diag_exc


def _normalize_surface_mapping(lay: dict) -> dict:
  mapping = normalize_surface_mapping(lay.get('mapping'), fallback=lay)
  lay = dict(lay or {})
  lay['mapping'] = mapping
  return canonicalize_surface_geometry(lay)


def _normalize_layout_keys(p: dict) -> dict:
  try:
    raw_surface = get_raw_surface_evidence(p)

    # Runtime normalization trusts canonical surface truth only. Legacy aliases
    # are migration-only and are stripped if they survived load-time migration.
    default_kind = 'cells' if int((raw_surface or {}).get('width') or 0) > 0 and int((raw_surface or {}).get('height') or 0) > 0 else 'strip'
    lay = build_surface_from_evidence(raw_surface, default_kind=default_kind)
    lay['kind'] = coerce_surface_kind(lay.get('kind'), default=default_kind)
    lay = _normalize_surface_mapping(lay)

    # Legacy matrix_* mapping aliases are migration-only. If they leaked this far,
    # strip them and let diagnostics report the survival elsewhere rather than
    # reviving runtime meaning from non-canonical keys here.

    for _k in ("type", "w", "h", "mw", "mh", "matrix_w", "matrix_h", "num_leds", "led_count",
               "matrix_serpentine", "matrix_flip_x", "matrix_flip_y", "matrix_rotate"):
      lay.pop(_k, None)

    p2 = dict(p or {})
    p2 = replace_project_root(p2, "surface", lay)
    p2.pop("layout", None)
    return p2
  except Exception as e:
    _pm_diag_exc(e, "return")
    return p


def _assert_no_legacy_layout_keys(p: dict) -> None:
  """Ensure legacy layout keys do not survive normalization.
  Legacy layout keys are import-only and must be migrated + removed.
  """
  try:
    raw_surface = get_raw_surface_evidence(p)
    if not isinstance(raw_surface, dict):
      return
    lay = dict(raw_surface)
    bad = []
    for k in ('w','h','mw','mh','matrix_w','matrix_h','num_leds','led_count'):
      if k in lay:
        bad.append(k)
        lay.pop(k, None)
    for k in ('matrix_serpentine','matrix_flip_x','matrix_flip_y','matrix_rotate'):
      if k in lay:
        bad.append(k)
        lay.pop(k, None)
    leaked_kind = get_surface_kind_value(raw_surface, default='')
    raw_kind = get_surface_kind_value(raw_surface, default='')
    if leaked_kind == 'cells' and raw_kind == 'matrix':
      bad.append('shape=cells-legacy-matrix')
    default_kind = 'cells' if int(lay.get('width') or 0) > 0 and int(lay.get('height') or 0) > 0 else 'strip'
    lay = build_surface_from_evidence(lay, default_kind=default_kind)
    kind = coerce_surface_kind(lay.get('kind'), default=default_kind)
    lay['kind'] = kind
    if 'type' in lay:
      bad.append(f"type={lay.get('type')}")
      lay.pop('type', None)
    lay = _normalize_surface_mapping(lay)
    if bad:
      p2 = dict(p or {})
      p2 = replace_project_root(p2, 'surface', lay)
      p2.pop('layout', None)
      p.clear(); p.update(p2)
      try:
        from runtime.diagnostics import GLOBAL_DIAGS
        GLOBAL_DIAGS.warn(domain='PROJECT', code='LEGACY_LAYOUT_KEYS_SURVIVED_NORMALIZE',
                          summary='Legacy layout keys survived normalization and were removed',
                          details={'keys': bad})
      except Exception:
        pass
  except Exception:
    return
