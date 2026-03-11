from __future__ import annotations

from app.project_canonical import apply_project_root

import time
import json
import hashlib
from typing import Callable

from qt.qt_compat import QtCore, QtGui, QtWidgets  # type: ignore
from core.surface_compat import get_surface_kind_value
from app.project_model import build_surface_dict, get_surface_snapshot, get_surface_kind, get_surface_count, get_surface_dimensions, get_surface_geometry_values


def _legacy_layer_param_mirror_keys() -> tuple[str, ...]:
    """Legacy params keys that should never mirror canonical layer fields.

    These keys remain diagnostics-only residue checks. Canonical composition
    fields live on the layer object itself, not under layer.params.
    """
    return (
        "layer_enabled",
        "layer_opacity",
        "layer_blend_mode",
        "layer_order",
    )

class DiagnosticsConsoleProbeReportsMixin:
    def _probe_triage(self) -> str:
        try:
            from app.triage_report import render_triage_report
            runtime = self._runtime_data()
            if callable(runtime):
                runtime = runtime()
            return render_triage_report(self.app_core.project, runtime=runtime)
        except Exception as e:
            return f"[Triage] ERROR: {e}"

    def _probe_full_health(self) -> str:
        try:
            from app.project_diagnostics import run_full_health_check
            return run_full_health_check(self.app_core.project, self.app_core, include_audio=False)
        except Exception as e:
            return f"[FullHealth] ERROR: {e}"

    def _probe_effect_audit(self) -> str:
        try:
            from app.effect_audit import run_effect_audit_detail
            return run_effect_audit_detail(self.app_core.project, include_audio=False, app_core=self.app_core)
        except Exception as e:
            return f"[EffectAudit] ERROR: {e}"

    def _probe_surface_mapping(self) -> str:
        try:
            from app.project_diagnostics import surface_mapping_inspector
            return surface_mapping_inspector(self.app_core.project)
        except Exception as e:
            return f"[Surface/Mapping] ERROR: {e}"

    def _probe_mapping_parity(self, mode: str) -> str:
        try:
            from app.mapping_parity_probe import run_mapping_parity_probe
            return run_mapping_parity_probe(self.app_core.project, mode=mode)
        except Exception as e:
            return f"[MappingParity:{mode}] ERROR: {e}"

    def _probe_mapping_parity_sweep(self) -> str:
        try:
            from app.mapping_parity_probe import run_mapping_parity_sweep
            return run_mapping_parity_sweep(self.app_core.project)
        except Exception as e:
            return f"[MappingParitySweep] ERROR: {e}"

    def _probe_layer_wiring(self) -> str:
        try:
            from app.project_diagnostics import layer_wiring_inspector
            return layer_wiring_inspector(self.app_core.project)
        except Exception as e:
            return f"[LayerWiring] ERROR: {e}"

    def _probe_layer_field_scan(self) -> str:
        try:
            from app.project_diagnostics import layer_field_probe
            return layer_field_probe(self.app_core.project)
        except Exception as e:
            return f"[LayerFieldProbe] ERROR: {e}"

    def _probe_resolver_inspector(self) -> str:
        try:
            from app.resolver_inspector import render_resolver_inspector
            return render_resolver_inspector(self.app_core.project)
        except Exception as e:
            return f"[ResolverInspector] ERROR: {e}"

    def _probe_canonical_registry(self) -> str:
        try:
            from app.resolver_inspector import render_registry_report
            return render_registry_report(getattr(self.app_core, "project", {}) or {})
        except Exception as e:
            return f"[CanonicalRegistry] ERROR: {e}"


    def _probe_ui_wiring_audit(self) -> str:
        try:
            from app.ui_wiring_audit import run_ui_wiring_audit
            return run_ui_wiring_audit(owner=self._owner_window(), app_core=self.app_core)
        except Exception as e:
            return f"[UIWiringAudit] ERROR: {e}"

    def _probe_preview_chain(self) -> str:
        try:
            from app.project_model import get_surface_snapshot, get_surface_kind, get_surface_geometry_values
            core = self.app_core
            proj = getattr(core, 'project', {}) or {}
            snap = get_surface_snapshot(proj)
            eng = getattr(core, '_full_preview_engine', None) or getattr(core, 'preview_engine', None)
            geom = getattr(core, '_full_preview_geom', None)
            lines = []
            lines.append(f"engine_present: {eng is not None}")
            if eng is not None:
                lines.append(f"engine_class: {eng.__class__.__name__}")
                lines.append(f"engine_has_render_frame: {hasattr(eng, 'render_frame')}")
                lines.append(f"engine_has_get_pixels: {hasattr(eng, 'get_pixels')}")
                try:
                    px = eng.get_pixels() if hasattr(eng, 'get_pixels') else None
                    lines.append(f"pixels_len: {len(px) if isinstance(px, (list, tuple)) else 'n/a'}")
                except Exception as e:
                    lines.append(f"get_pixels_error: {type(e).__name__}: {e}")
            lines.append(f"preview_dirty: {bool(getattr(core, '_preview_dirty', False))}")
            lines.append(f"preview_sync_last_error: {getattr(core, '_preview_sync_last_error', None)}")
            lines.append(f"full_preview_last_error: {getattr(core, '_full_preview_last_error', None)}")
            if geom is not None:
                lines.append(f"geom_class: {geom.__class__.__name__}")
            lines.append(f"surface_snapshot: {json.dumps(snap, indent=2, sort_keys=False)}")
            owner = self._owner_window()
            alias_ids = {}
            for attr in ('surface_preview_widget','matrix_preview_widget','strip_preview_widget','preview_widget','matrix_widget'):
                w = (getattr(core, attr, None) or (getattr(owner, attr, None) if owner is not None else None))
                if w is not None:
                    alias_ids.setdefault(id(w), []).append(attr)
            for attrs in alias_ids.values():
                w = (getattr(core, attrs[0], None) or (getattr(owner, attrs[0], None) if owner is not None else None))
                try:
                    lines.append(f"widget[{','.join(attrs)}]: {w.__class__.__name__} visible={w.isVisible()} size={w.width()}x{w.height()}")
                except Exception:
                    lines.append(f"widget[{','.join(attrs)}]: {w.__class__.__name__}")
            try:
                if owner is not None and getattr(owner, 'strip_mini', None) is not None:
                    sm = owner.strip_mini
                    lines.append(f"strip_mini_visible: {sm.isVisible()} size={sm.width()}x{sm.height()}")
                if owner is not None and getattr(owner, 'strip_header', None) is not None:
                    sh = owner.strip_header
                    lines.append(f"strip_header_visible: {sh.isVisible()} size={sh.width()}x{sh.height()}")
                if owner is not None and getattr(owner, 'preview_stack', None) is not None:
                    ps = owner.preview_stack
                    lines.append(f"preview_stack_visible: {ps.isVisible()} currentIndex={ps.currentIndex()} size={ps.width()}x{ps.height()}")
            except Exception:
                pass
            return "\n".join(lines)
        except Exception as e:
            return f"[PreviewChain] ERROR: {e}"

    def _probe_preview_display_assertion(self) -> str:
        try:
            owner = self._owner_window()
            snap = get_surface_snapshot(getattr(self.app_core, 'project', {}) or {})
            kind = str(get_surface_kind(getattr(self.app_core, 'project', {}) or {}) or 'strip').lower()
            lines = []
            ok = True
            lines.append(f"surface_kind: {kind}")
            sh_vis = None
            ps_vis = None
            ps_idx = None
            if owner is not None and getattr(owner, 'strip_header', None) is not None:
                sh_vis = bool(owner.strip_header.isVisible())
            if owner is not None and getattr(owner, 'preview_stack', None) is not None:
                ps_vis = bool(owner.preview_stack.isVisible())
                ps_idx = int(owner.preview_stack.currentIndex())
            lines.append(f"strip_header_visible: {sh_vis}")
            lines.append(f"preview_stack_visible: {ps_vis}")
            lines.append(f"preview_stack_index: {ps_idx}")
            if kind == 'strip':
                if sh_vis is not True or ps_vis is not False:
                    ok = False
                lines.append("expected: strip header visible, preview stack hidden")
            else:
                if sh_vis is not False or ps_vis is not True or ps_idx != 0:
                    ok = False
                lines.append("expected: strip header hidden, preview stack visible on cells page")
            try:
                eng = getattr(self.app_core, '_full_preview_engine', None) or getattr(self.app_core, 'preview_engine', None)
                px = eng.get_pixels() if (eng is not None and hasattr(eng, 'get_pixels')) else None
                non_black = 0
                if isinstance(px, (list, tuple)):
                    for p in px:
                        try:
                            if isinstance(p, (list, tuple)) and any(float(v) > 0 for v in p[:3]):
                                non_black += 1
                            elif isinstance(p, (int, float)) and p > 0:
                                non_black += 1
                        except Exception:
                            pass
                lines.append(f"non_black_pixels: {non_black}")
            except Exception as e:
                lines.append(f"non_black_pixels_error: {type(e).__name__}: {e}")
            lines.append(f"result: {'OK' if ok else 'FAIL'}")
            return "\n".join(lines)
        except Exception as e:
            return f"[PreviewDisplayAssertion] ERROR: {e}"

    def _probe_per_cell_render_assertion(self) -> str:
        try:
            import copy
            import time
            from preview.preview_project_bridge import make_preview_engine_from_project_dict
            from app.project_model import get_surface_snapshot, get_surface_kind, get_surface_geometry_values
            proj = copy.deepcopy(getattr(self.app_core, 'project', {}) or {})
            surface = get_surface_snapshot(proj) or {}
            kind, count, width, height = get_surface_geometry_values(surface, default_kind='strip', default_count=1)
            layers = list((proj.get('layers') or []))
            test_layer = {
                'id': '__diag_cell_assert__',
                'name': 'Diagnostics Solid Assert',
                'behavior': 'solid',
                'enabled': True,
                'opacity': 1.0,
                'blend_mode': 'over',
                'params': {'color': (255, 0, 0), 'brightness': 1.0},
            }
            layers.append(test_layer)
            proj, _, _ = apply_project_root(proj, 'layers', layers)
            eng, _, _ = make_preview_engine_from_project_dict(proj, audio=getattr(self.app_core, 'audio', None), fixed_dt=1.0/60.0, signal_bus=getattr(self.app_core, 'signal_bus', None), root_dir=getattr(getattr(self.app_core, 'pm', None), 'root_dir', None))
            eng.render_frame(time.time())
            px = eng.get_pixels() if hasattr(eng, 'get_pixels') else []
            non_black = 0
            fully_lit = 0
            bad_idx = []
            if isinstance(px, (list, tuple)):
                for i, p in enumerate(px):
                    try:
                        rgb = tuple(int(v) for v in p[:3]) if isinstance(p, (list, tuple)) else (int(p), 0, 0)
                    except Exception:
                        rgb = (0, 0, 0)
                    if any(v > 0 for v in rgb):
                        non_black += 1
                    if rgb == (255, 0, 0):
                        fully_lit += 1
                    else:
                        if len(bad_idx) < 12:
                            bad_idx.append(f'{i}:{rgb}')
            ok = (len(px) == count and non_black == count and fully_lit == count)
            lines = []
            lines.append(f'surface_kind: {kind}')
            lines.append(f'expected_cells: {count}')
            lines.append(f'pixels_len: {len(px) if isinstance(px, (list, tuple)) else "n/a"}')
            lines.append(f'non_black_pixels: {non_black}')
            lines.append(f'fully_lit_pixels: {fully_lit}')
            lines.append('expected_color: (255, 0, 0)')
            if bad_idx:
                lines.append('sample_mismatches: ' + ', '.join(bad_idx))
            lines.append('result: ' + ('OK' if ok else 'FAIL'))
            return '\n'.join(lines)
        except Exception as e:
            return f'[PerCellRenderAssertion] ERROR: {type(e).__name__}: {e}'

    def _probe_widget_paint_proof(self) -> str:
        try:
            from qt.qt_compat import QtWidgets, QtGui
            owner = self._owner_window()
            lines = ["=== Widget Paint Proof ==="]
            if owner is None:
                return "\n".join(lines + ["result: FAIL", "reason: owner window missing"])
            snap = get_surface_snapshot(getattr(self.app_core, 'project', {}) or {})
            kind = str(get_surface_kind(getattr(self.app_core, 'project', {}) or {}) or 'strip').lower()
            lines.append(f"surface_kind: {kind}")
            target = getattr(owner, 'strip_mini', None) if kind == 'strip' else getattr(owner, 'preview_widget', None)
            if target is None:
                return "\n".join(lines + ["result: FAIL", "reason: target widget missing"])
            w = max(1, int(target.width() or 0))
            h = max(1, int(target.height() or 0))
            lines.append(f"target_widget: {type(target).__name__} visible={target.isVisible()} size={w}x{h}")
            orig = getattr(target, '_get_current_frame', None)
            def fake_frame():
                surface_cfg = build_surface_dict(
                    kind='strip' if kind == 'strip' else 'cells',
                    count=144,
                    width=16,
                    height=16,
                    mapping={'serpentine': False, 'flip_x': False, 'flip_y': False, 'rotate': 0, 'origin': 'top_left'},
                )
                _k, count, width, height = get_surface_geometry_values(surface_cfg, default_kind='cells', default_count=1)
                return {
                    'width': width,
                    'height': height,
                    'pixels': [(255,0,0)] * count,
                    'mapping': dict(surface_cfg.get('mapping') or {}),
                }
            target._get_current_frame = fake_frame
            try:
                target.update()
                target.repaint()
                QtWidgets.QApplication.processEvents()
                pm = target.grab()
                img = pm.toImage()
                redish = 0
                nonblack = 0
                samples = []
                for y in range(0, img.height(), max(1, img.height() // 24)):
                    for x in range(0, img.width(), max(1, img.width() // 96)):
                        c = img.pixelColor(x, y)
                        rgb = (c.red(), c.green(), c.blue())
                        if any(v > 0 for v in rgb):
                            nonblack += 1
                        if c.red() > 150 and c.green() < 80 and c.blue() < 80:
                            redish += 1
                        if len(samples) < 12:
                            samples.append(f"{x},{y}:{rgb}")
                lines.append(f"sampled_non_black_points: {nonblack}")
                lines.append(f"sampled_redish_points: {redish}")
                lines.append("sample_points: " + ", ".join(samples))
                ok = redish > 0
                lines.append('result: ' + ('OK' if ok else 'FAIL'))
                if not ok:
                    lines.append('reason: painted widget grab did not show visible red content')
            finally:
                if orig is not None:
                    target._get_current_frame = orig
                elif hasattr(target, '_get_current_frame'):
                    try:
                        delattr(target, '_get_current_frame')
                    except Exception:
                        pass
            return "\n".join(lines)
        except Exception as e:
            return f'[WidgetPaintProof] ERROR: {type(e).__name__}: {e}'

    def _probe_visible_strip_preview_proof(self) -> str:
        try:
            import copy, time
            from preview.preview_project_bridge import make_preview_engine_from_project_dict
            from app.project_model import get_surface_snapshot, get_surface_kind, get_surface_geometry_values
            owner = self._owner_window()
            proj = copy.deepcopy(getattr(self.app_core, 'project', {}) or {})
            surface = get_surface_snapshot(proj) or {}
            lines = []
            kind = get_surface_kind_value(surface or {'kind': get_surface_kind(proj) or 'strip'}, default='strip')
            lines.append(f"surface_kind: {kind}")
            if kind != 'strip':
                lines.append('result: SKIPPED (strip-only proof)')
                return '\n'.join(lines)
            layers = list((proj.get('layers') or []))
            layers.append({
                'id': '__diag_visible_preview__',
                'name': 'Diagnostics Visible Preview Proof',
                'behavior': 'solid',
                'enabled': True,
                'opacity': 1.0,
                'blend_mode': 'over',
                'params': {'color': (255, 0, 0), 'brightness': 1.0},
            })
            proj, _, _ = apply_project_root(proj, 'layers', layers)
            eng, _, _ = make_preview_engine_from_project_dict(proj, audio=getattr(self.app_core, 'audio', None), fixed_dt=1.0/60.0, signal_bus=getattr(self.app_core, 'signal_bus', None), root_dir=getattr(getattr(self.app_core, 'pm', None), 'root_dir', None))
            eng.render_frame(time.time())
            px = eng.get_pixels() if hasattr(eng, 'get_pixels') else []
            non_black = 0
            if isinstance(px, (list, tuple)):
                for p in px:
                    try:
                        rgb = tuple(int(v) for v in p[:3]) if isinstance(p, (list, tuple)) else (int(p),0,0)
                    except Exception:
                        rgb=(0,0,0)
                    if any(v > 0 for v in rgb):
                        non_black += 1
            lines.append(f"engine_non_black_pixels: {non_black}")
            try:
                if owner is not None and getattr(owner, 'strip_mini', None) is not None:
                    sm = owner.strip_mini
                    lines.append(f"strip_mini_visible: {sm.isVisible()} size={sm.width()}x{sm.height()}")
                    lines.append('strip_header_height_recommendation: 48px active')
                if owner is not None and getattr(owner, 'strip_header', None) is not None:
                    sh = owner.strip_header
                    lines.append(f"strip_header_visible: {sh.isVisible()} size={sh.width()}x{sh.height()}")
            except Exception:
                pass
            lines.append('result: ' + ('OK' if non_black > 0 else 'FAIL'))
            lines.append('note: proof uses a temporary solid-red frame to confirm user-visible strip preview conditions')
            return '\n'.join(lines)
        except Exception as e:
            return f'[VisibleStripPreviewProof] ERROR: {type(e).__name__}: {e}'

    def _probe_dump_ui_layout(self) -> str:
        try:
            # Reuse the existing diagnostics tab helper if present
            from qt.diagnostics_tab import dump_ui_layout_strip_preview
            return dump_ui_layout_strip_preview(self._owner_window())
        except Exception as e:
            return f"[DumpUI] ERROR: {e}"

    def _runtime_data(self) -> dict:
        runtime = {}
        try:
            if hasattr(self.app_core, 'get_runtime_variables_state'):
                rv = self.app_core.get_runtime_variables_state()
                if isinstance(rv, dict):
                    runtime['variables'] = rv
        except Exception:
            pass
        try:
            if hasattr(self.app_core, 'get_signal_snapshot'):
                sigs = self.app_core.get_signal_snapshot()
                if isinstance(sigs, dict):
                    runtime['signals'] = sigs
        except Exception:
            pass
        return runtime

            # ---- Heartbeat / status ----
