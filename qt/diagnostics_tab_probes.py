
from __future__ import annotations

import json
import traceback

try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None


def _diag_exc(error: Exception, where: str):
    try:
        if _DIAGS is not None:
            _DIAGS.exception(error, domain="UI", code="QT_UI_EXCEPTION", summary=where)
    except Exception:
        pass

from qt.diagnostics_tab_helpers import pretty_text as _pretty
from core.surface_compat import get_surface_kind_value


class DiagnosticsTabProbeMixin:

    def _run_ui_wiring_audit(self):
            self._diag_bump("UI Wiring Audit")
            try:
                from app.ui_wiring_audit import run_ui_wiring_audit
                owner = None
                try:
                    owner = self.window() if hasattr(self, "window") else None
                except Exception:
                    owner = None
                report = run_ui_wiring_audit(owner=owner, app_core=self.app_core)
                self._set_probe_text(report)
            except Exception:
                self._set_probe_text("UI wiring audit failed.\n" + traceback.format_exc())
    def _dump_runtime_diags(self):
            """Dump tail of runtime.diagnostics.GLOBAL_DIAGS into Probe Output."""
            try:
                from runtime.diagnostics import GLOBAL_DIAGS
                tail = GLOBAL_DIAGS.tail(30)
                out = []
                out.append(f"GLOBAL_DIAGS: last {len(tail)} events (dropped={getattr(GLOBAL_DIAGS, 'dropped', 0)})")
                for ev in tail:
                    try:
                        out.append(
                            f"[{ev.level}] {ev.domain}/{ev.kind} {ev.code} frame={ev.frame} :: {ev.summary}"
                        )
                        if getattr(ev, 'exc_type', None) or getattr(ev, 'exc_msg', None):
                            out.append(f"  exc: {ev.exc_type}: {ev.exc_msg}")
                        det = getattr(ev, 'details', None)
                        if isinstance(det, dict) and det:
                            out.append(f"  details: {json.dumps(det, indent=2, sort_keys=False)}")
                    except Exception:
                        out.append(str(ev))
                self._set_probe_text("\n".join(out) + "\n")
            except Exception:
                self._set_probe_text("Runtime diagnostics unavailable.\n" + traceback.format_exc())

    def _run_mapping_pattern_probe(self):
            self._diag_bump("Mapping Pattern Probe (coords)")
            try:
                proj = self._project_data()
                from app.mapping_parity_probe import run_mapping_pattern_probe
                report = run_mapping_pattern_probe(proj)
                self._set_probe_text(report)
            except Exception as e:
                self._set_probe_text(f"Mapping Pattern Probe ERROR:\n{e}")

    def _run_project_roundtrip_probe(self):
            self._diag_bump("Project Round-trip Probe")
            try:
                proj = self._project_data()
                from app.project_roundtrip_probe import run_project_roundtrip_probe, format_probe_result
                res = run_project_roundtrip_probe(proj)
                self._set_probe_text(format_probe_result(res))
            except Exception:
                self._set_probe_text("Project round-trip probe failed.\n" + traceback.format_exc())

    def _run_composition_parity_probe(self):
            self._diag_bump("Composition Parity Cases")
            try:
                from app.composition_parity_probe import run_probe
                bid = ""
                try:
                    bid = str(getattr(self.app_core, "app_id", "") or "")
                except Exception:
                    bid = ""
                res = run_probe(app_id=bid, diagnostics=_DIAGS)
                self._set_probe_text(_pretty(res))
            except Exception as e:
                _diag_exc(e, "qt/diagnostics_tab.py:_run_composition_parity_probe")
                self._set_probe_text("Composition parity probe failed:\n" + traceback.format_exc())

    def _run_mapping_parity_cases(self):
            self._diag_bump('Mapping Parity Cases')
            try:
                proj = self._project_data()
                from app.mapping_parity_probe import run_mapping_parity_cases
                report = run_mapping_parity_cases(proj)
                self._set_probe_text(report)
            except Exception as e:
                self._set_probe_text(f"Mapping Parity Cases ERROR:\n{e}\n" + traceback.format_exc())

    def _run_mapping_parity_compat(self):
            """Compatibility wrapper for older signal hookups."""
            return self._run_mapping_parity_cases()

    def _run_mapping_parity_matrix(self):
            """Compatibility wrapper for older signal hookups."""
            return self._run_mapping_parity_compat()


    def _run_resolver_priority_probe(self):
            self._diag_bump("Override Priority Probe")
            try:
                runner = getattr(self, "_probe_override_priority", None)
                if callable(runner):
                    self._set_probe_text(str(runner()))
                    return
                self._set_probe_text("Override priority probe unavailable: missing diagnostics override probe wiring.")
            except Exception:
                self._set_probe_text("Override priority probe failed.\n" + traceback.format_exc())

    def _run_rules_parity_cases(self):
            self._diag_bump("Rules Parity Cases")
            try:
                from app.rules_parity_probe import run_cases
                bid = ""
                try:
                    bid = str(getattr(self.app_core, "app_id", "") or "")
                except Exception:
                    bid = ""
                res = run_cases(app_id=bid, diagnostics=_DIAGS)
                self._set_probe_text(_pretty(res))
            except Exception as e:
                _diag_exc(e, "qt/diagnostics_tab.py:_run_rules_parity_cases")
                self._set_probe_text("Rules Parity Cases failed:\n" + traceback.format_exc())

    def _run_rules_parity_probe(self):
            self._diag_bump("Rules Parity Probe")
            try:
                from app.rules_parity_probe import run_probe
                bid = ""
                try:
                    bid = str(getattr(self.app_core, "app_id", "") or "")
                except Exception:
                    bid = ""
                res = run_probe(app_id=bid, diagnostics=_DIAGS)
                self._set_probe_text(_pretty(res))
            except Exception as e:
                _diag_exc(e, "qt/diagnostics_tab.py:_run_rules_parity_probe")
                try:
                    self._set_probe_text("Rules Parity Probe failed:\n" + traceback.format_exc())
                except Exception:
                    pass

    def _run_kernel_export_probe(self):
            """Run a lightweight export codegen probe for Kernel layers."""
            try:
                from app.kernel_export_probe import run_kernel_export_probe
                res = run_kernel_export_probe()
                import json
                out = []
                out.append(f"Kernel Export Probe: {res.summary}")
                out.append(json.dumps(res.evidence, indent=2, sort_keys=False))
                self._set_probe_text("\n".join(out) + "\n")
            except Exception:
                self._set_probe_text("Kernel export probe failed.\n" + traceback.format_exc())

    def _run_health(self):
            try:
                from app.project_diagnostics import run_full_health_check
                report = run_full_health_check(
                    self._project_data(),
                    app_core=self.app_core,
                    controller=self.controller,
                )
                self._set_probe_text(_pretty(report))
            except Exception:
                tb = traceback.format_exc()
                self._set_probe_text("Health check failed:\n\n" + tb)

    def _run_audit(self):
            try:
                include_audio = bool(self.chk_audio.isChecked())
                from app.effect_audit import run_effect_audit_detail
                report = run_effect_audit_detail(
                    self._project_data(),
                    include_audio=include_audio,
                    app_core=self.app_core,
                    controller=self.controller,
                )
                self._set_probe_text(_pretty(report))
            except Exception:
                tb = traceback.format_exc()
                self._set_probe_text("Effect audit failed:\n\n" + tb)

    def _dump_ui(self):
            try:
                app = qapplication_instance()
                if app is None:
                    self._set_probe_text("UI dump failed: QApplication.instance is None")
                    return

                widgets = list(all_widgets())

                def match(w) -> bool:
                    try:
                        cls = w.__class__.__name__.lower()
                    except Exception:
                        cls = ""
                    try:
                        name = (w.objectName() or "").lower()
                    except Exception:
                        name = ""
                    # conservative: only pick likely preview/strip widgets
                    keys = [
                        "strip",
                        "previewbar",
                        "minipreview",
                        "previewwidget",
                        "viewport",
                        "canvas",
                    ]
                    return any(k in cls for k in keys) or any(k in name for k in keys)

                hits = [w for w in widgets if match(w)]

                lines = []
                lines.append("=== UI LAYOUT DUMP (Strip/Preview) ===")
                lines.append(f"widgets_total: {len(widgets)}")
                lines.append(f"matches: {len(hits)}")
                lines.append("")

                # Sort by class then objectName for stability
                def _key(w):
                    try:
                        cn = w.__class__.__name__
                    except Exception:
                        cn = ""
                    try:
                        on = w.objectName() or ""
                    except Exception:
                        on = ""
                    return (cn.lower(), on.lower())

                for w in sorted(hits, key=_key):
                    try:
                        cn = w.__class__.__name__
                    except Exception:
                        cn = str(type(w))
                    try:
                        on = w.objectName() or ""
                    except Exception:
                        on = ""

                    try:
                        vis = bool(w.isVisible())
                    except Exception:
                        vis = False
                    try:
                        hid = bool(w.isHidden())
                    except Exception:
                        hid = False

                    try:
                        geo = w.geometry
                        geo_s = f"{geo.x()},{geo.y()} {geo.width()}x{geo.height()}"
                    except Exception:
                        geo_s = "(geo n/a)"

                    try:
                        sh = w.sizeHint
                        sh_s = f"{sh.width()}x{sh.height()}"
                    except Exception:
                        sh_s = "(sizeHint n/a)"

                    try:
                        mh = w.minimumHeight()
                        xh = w.maximumHeight()
                        ch = w.height()
                        hw = f"minH={mh} maxH={xh} curH={ch}"
                    except Exception:
                        hw = "(height n/a)"

                    label = ""
                    if cn == "StripPreviewBar":
                        label = " (strip header container)"
                    elif cn == "StripMiniPreview":
                        label = " (actual strip preview line)"
                    elif cn == "MatrixPreviewWidget":
                        label = " (cells preview)"
                    elif cn == "PreviewWidget":
                        label = " (legacy preview canvas — strip mode uses StripMiniPreview)"

                    lines.append(f"- {cn}{label} name='{on}' visible={vis} hidden={hid}")
                    lines.append(f"  geo: {geo_s}  sizeHint: {sh_s}  {hw}")
                    lines.append(f"  parents: {_parent_chain(w)}")

                    # If it's a splitter child, show sizes
                    try:
                        pw = w.parentWidget()
                        if pw is not None and pw.__class__.__name__.lower().find('splitter') >= 0:
                            try:
                                sizes = pw.sizes()
                                lines.append(f"  parentSplitter.sizes: {list(sizes)}")
                            except Exception as e:
                                _diag_exc(e, "qt/diagnostics_tab.py")
                    except Exception as e:
                        _diag_exc(e, "qt/diagnostics_tab.py")

                if len(hits) == 0:
                    lines.append("(No matching widgets found. If your strip bar class is renamed, add its class/objectName keyword to the matcher.)")

                self.out.setPlainText("\n".join(lines))
            except Exception:
                tb = traceback.format_exc()
                self.out.setPlainText("UI dump failed:\n\n" + tb)

    def _dump_audio(self):
            try:
                lines = []
                lines.append("=== AUDIO WIRING DUMP ===")

                candidates = []
                if self.controller is not None:
                    candidates.append(("controller", self.controller))
                    br = getattr(self.controller, "bridge", None)
                    if br is not None:
                        candidates.append(("controller.bridge", br))
                if self.app_core is not None:
                    candidates.append(("app_core", self.app_core))
                    br2 = getattr(self.app_core, "bridge", None)
                    if br2 is not None:
                        candidates.append(("app_core.bridge", br2))

                seen = set()
                for label, obj in candidates:
                    if obj is None:
                        continue
                    oid = id(obj)
                    if oid in seen:
                        continue
                    seen.add(oid)
                    lines.append("")
                    lines.append(f"-- {label}: {obj.__class__.__name__} --")

                    # common fields
                    for k in [
                        "preview_audio_mode",
                        "preview_audio_backend",
                        "preview_audio_status",
                    ]:
                        if hasattr(obj, k):
                            try:
                                lines.append(f"{k}: {getattr(obj, k)}")
                            except Exception:
                                lines.append(f"{k}: (error)")

                    # audio_service backend
                    svc = getattr(obj, "audio_service", None)
                    if svc is not None:
                        lines.append(f"audio_service: {svc.__class__.__name__}")
                        for k in ["backend", "status", "mode"]:
                            if hasattr(svc, k):
                                try:
                                    lines.append(f"audio_service.{k}: {getattr(svc, k)}")
                                except Exception as e:
                                    _diag_exc(e, "qt/diagnostics_tab.py")

                    # preview engine last audio
                    eng = getattr(obj, "preview_engine", None)
                    if eng is not None:
                        lines.append(f"preview_engine: {eng.__class__.__name__}")
                        st = getattr(eng, "last_audio_state", None)
                        if isinstance(st, dict):
                            lines.append(f"last_audio_state.keys: {sorted(list(st.keys()))}")
                            if "energy" in st:
                                lines.append(f"energy: {st.get('energy')}")
                            if "mono" in st:
                                try:
                                    lines.append(f"mono[0:7]: {list(st.get('mono') or [])[:7]}")
                                except Exception:
                                    lines.append(f"mono: {st.get('mono')}")
                        sb = getattr(eng, "signal_bus", None)
                        if sb is not None and hasattr(sb, "frame"):
                            try:
                                lines.append(f"signal_bus.frame: {getattr(sb, 'frame')}")
                            except Exception as e:
                                _diag_exc(e, "qt/diagnostics_tab.py")

                self.out.setPlainText("\n".join(lines))
            except Exception:
                tb = traceback.format_exc()
                self.out.setPlainText("Audio dump failed:\n\n" + tb)

    def _dump_surface_mapping(self):
            self._diag_bump("Surface/Mapping Inspector ")
            try:
                # : Surface/Mapping inspector must show canonical resolver-derived truth.
                # Raw surface is shown as evidence, and any leaked root layout keys are listed separately. The "truth" is the resolver.
                proj = self._project_data()
                from app.project_model import get_surface_evidence_bundle, get_surface_snapshot, get_surface_kind, get_surface_mapping, get_surface_count, get_surface_dimensions
                evidence = get_surface_evidence_bundle(proj)
                raw_surface = evidence.get('raw_surface') if isinstance(evidence, dict) else {}
                leaked_layout = evidence.get('leaked_layout') if isinstance(evidence, dict) else {}
                from runtime.resolver import resolve_address

                snap = get_surface_snapshot(proj)

                # Canonical surface fields (resolver truth)
                kind_r = resolve_address(project=proj, address='project.surface.kind', default='strip')
                count_r = resolve_address(project=proj, address='project.surface.count', default=0)
                width_r = resolve_address(project=proj, address='project.surface.width', default=0)
                height_r = resolve_address(project=proj, address='project.surface.height', default=0)
                serp_r = resolve_address(project=proj, address='project.surface.mapping.serpentine', default=False)
                fx_r = resolve_address(project=proj, address='project.surface.mapping.flip_x', default=False)
                fy_r = resolve_address(project=proj, address='project.surface.mapping.flip_y', default=False)
                rot_r = resolve_address(project=proj, address='project.surface.mapping.rotate', default=0)
                org_r = resolve_address(project=proj, address='project.surface.mapping.origin', default='top_left')

                kind = get_surface_kind_value(snap or {'kind': (get_surface_kind(proj) or kind_r.value or 'strip')}, default='strip')
                n = int(get_surface_count(proj) or count_r.value or snap.get('count') or 0)
                w, h = get_surface_dimensions(proj)
                mapping = get_surface_mapping(proj)

                # Detect legacy / shadow keys still present in leaked raw layout (should trend to empty)
                legacy_keys = []
                try:
                    if isinstance(leaked_layout, dict):
                        for k in (
                            'matrix_serpentine', 'matrix_flip_x', 'matrix_flip_y', 'matrix_rotate',
                        ):
                            if k in leaked_layout:
                                legacy_keys.append(k)
                except Exception:
                    legacy_keys = []

                out = []
                out.append("== Surface/Mapping Inspector ( canonical resolver truth) ==")
                out.append("canonical (resolver):")
                out.append(f"- project.surface.kind: {kind}  (source={kind_r.source})")
                out.append(f"- project.surface.count: {n}  (source={count_r.source})")
                out.append(f"- project.surface.width: {w}  (source={width_r.source})")
                out.append(f"- project.surface.height: {h}  (source={height_r.source})")
                out.append(f"- project.surface.mapping.serpentine: {mapping.get('serpentine')}  (source={serp_r.source})")
                out.append(f"- project.surface.mapping.flip_x: {mapping.get('flip_x')}  (source={fx_r.source})")
                out.append(f"- project.surface.mapping.flip_y: {mapping.get('flip_y')}  (source={fy_r.source})")
                out.append(f"- project.surface.mapping.rotate: {mapping.get('rotate')}  (source={rot_r.source})")
                out.append(f"- project.surface.mapping.origin: {mapping.get('origin')}  (source={org_r.source})")
                out.append("")
                out.append("legacy root-layout residue present in evidence only:")
                if legacy_keys:
                    out.append("- " + ", ".join(sorted(legacy_keys)))
                else:
                    out.append("- (none found)")
                out.append("")
                out.append("raw surface evidence only (not canonical truth):")
                try:
                    out.append(self._safe_json(raw_surface))
                except Exception:
                    out.append(str(raw_surface))
                out.append("")
                out.append("leaked root layout evidence only (migration residue, not canonical truth):")
                try:
                    out.append(self._safe_json(leaked_layout))
                except Exception:
                    out.append(str(leaked_layout))

                self._set_probe_text("\n".join(out))
            except Exception as e:
                self._set_probe_text(f"Surface/Mapping Inspector ERROR:\n{e}")

    def _run_mapping_parity_probe(self, mode: str = "full"):
            self._diag_bump(f"Mapping Parity ({mode})")
            try:
                proj = self._project_data()
                from app.mapping_parity_probe import run_project_mapping_parity_probe
                report = run_project_mapping_parity_probe(proj, mode=mode)
                self._set_probe_text(report)
            except Exception as e:
                self._set_probe_text(f"Mapping Parity ({mode}) ERROR:\n{e}")

    def _run_mapping_parity_sweep(self):
            self._diag_bump('Mapping Parity (Flags Sweep)')
            try:
                proj = self._project_data()
                from app.mapping_parity_probe import run_mapping_parity_sweep
                report = run_mapping_parity_sweep(proj)
                self._set_probe_text(report)
            except Exception as e:
                self._set_probe_text(f"Mapping Parity (Flags Sweep) ERROR:\n{e}")

    def _dump_resolver_inspector(self):
            self._diag_bump('Resolver Inspector ')
            try:
                from app.resolver_inspector import render_resolver_inspector
                proj = self._project_data()
                self._set_probe_text(render_resolver_inspector(proj))
            except Exception as e:
                self._set_probe_text(f"Resolver Inspector ERROR:\n{e}")

    def _run_triage_summary(self):
            self._diag_bump('Triage ')
            try:
                from app.triage_report import render_triage_report
                proj = self._project_data()
                self._set_probe_text(render_triage_report(proj, runtime=self._runtime_data()))
            except Exception as e:
                self._set_probe_text(f"Triage Summary ERROR:\n{e}")

    def _dump_canonical_registry(self):
            self._diag_bump('Canonical Address Registry ')
            try:
                from app.resolver_inspector import render_registry_report
                self._set_probe_text(render_registry_report(self._project_data()))
            except Exception as e:
                self._set_probe_text(f"Canonical Address Registry ERROR:\n{e}")

    def _run_preview_chain_probe(self):
            self._diag_bump('Preview Chain Inspector')
            try:
                lines = []
                core = self.app_core
                proj = self._project_data()
                try:
                    from app.project_model import get_surface_snapshot, get_surface_kind, get_surface_mapping, get_surface_count, get_surface_dimensions
                    snap = get_surface_snapshot(proj)
                except Exception:
                    snap = {}
                eng = getattr(core, '_full_preview_engine', None) or getattr(core, 'preview_engine', None)
                lines.append('=== Preview Chain Inspector ===')
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
                lines.append('surface_snapshot:')
                lines.append(self._safe_json(snap))
                self._set_probe_text('\n'.join(lines))
            except Exception as e:
                self._set_probe_text(f"Preview Chain Inspector ERROR:\n{e}\n\n" + traceback.format_exc())

    def _dump_layer_wiring(self):
            self._diag_bump('Layer Wiring Inspector ')
            try:
                from app.project_diagnostics import layer_wiring_inspector
                proj = self._project_data()
                self._set_probe_text(layer_wiring_inspector(proj))
            except Exception as e:
                self._set_probe_text(f'Layer Wiring Inspector ERROR:\n{e}')

    def _run_layer_field_probe(self):
            self._diag_bump('Layer Field Probe ')
            try:
                from app.project_diagnostics import layer_field_probe_code_scan
                # run_root is project root (two levels above this file)
                import os
                run_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                self._set_probe_text(layer_field_probe_code_scan(run_root))
            except Exception as e:
                self._set_probe_text(f'Layer Field Probe ERROR:\n{e}')


    def _run_rules_parity_compat(self):
            """Compatibility wrapper for older signal hookups."""
            return self._run_rules_parity_cases()

    def _run_rules_parity_matrix(self):
            """Compatibility wrapper for older signal hookups."""
            return self._run_rules_parity_compat()
