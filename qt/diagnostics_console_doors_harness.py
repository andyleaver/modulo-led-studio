from __future__ import annotations
from app.project_canonical import apply_project_roots
from app.project_model import get_surface_snapshot, build_surface_dict
import time

from qt.diagnostics_console_doors_utils import DiagnosticsConsoleDoorsUtilityMixin
from qt.diagnostics_console_doors_probes import DiagnosticsConsoleDoorsProbeMixin

class DiagnosticsConsoleDoorsHarnessMixin:
        def _run_opacity_toggle_harness(self) -> None:
            """Harness: SOLID GREEN base + SOLID RED overlay toggled @ ~1Hz (tick)."""
            self._log("\n=== OPACITY TOGGLE HARNESS (GREEN BASE / RED TOGGLE) ===")
            core = getattr(self, 'app_core', None)
            if core is None:
                self._log("FAIL: app_core missing")
                return

            try:
                p0 = dict(getattr(core, 'project', {}) or {})
            except Exception:
                p0 = {}

            surface = get_surface_snapshot(p0)
            # Harnesses must derive runtime geometry from canonical surface truth.
            # Raw project.surface is evidence territory; leaked root layout is migration residue only.
            if not isinstance(surface, dict) or not surface:
                surface = build_surface_dict(kind='strip', count=144)

            ts = int(time.time() * 1000)

            layers = [
                {
                    'uid': f'layer_{ts}_0',
                    'name': 'SOLID GREEN (base)',
                    'behavior': 'solid',
                    'params': {'color': [0, 255, 0]},
                    'opacity': 1.0,
                    'enabled': True,
                    'blend_mode': 'over',
                    'order': 0,
                },
                {
                    'uid': f'layer_{ts}_1',
                    'name': 'SOLID RED (toggled)',
                    'behavior': 'solid',
                    'params': {'color': [255, 0, 0]},
                    'opacity': 0.0,
                    'enabled': True,
                    'blend_mode': 'over',
                    'order': 1,
                },
            ]

            rules = [
                {
                    'id': 'r_red_on',
                    'enabled': True,
                    'name': 'Red ON while square1hz',
                    'trigger': 'tick',
                    'trigger_mode': 'all',
                    'conditions': [ {'signal': 'time.square1hz', 'op': '>', 'value': 0.5} ],
                    'action': {'kind': 'set_layer_param', 'layer': 1, 'param': 'opacity', 'expr': {'src':'const','const':1.0}},
                },
                {
                    'id': 'r_red_off',
                    'enabled': True,
                    'name': 'Red OFF while square1hz_inv',
                    'trigger': 'tick',
                    'trigger_mode': 'all',
                    'conditions': [ {'signal': 'time.square1hz_inv', 'op': '>', 'value': 0.5} ],
                    'action': {'kind': 'set_layer_param', 'layer': 1, 'param': 'opacity', 'expr': {'src':'const','const':0.0}},
                },
            ]

            p = dict(p0)
            ui = dict(p.get('ui') or {})
            ui['selected_layer'] = 1
            variables = dict(p.get('variables') or {'number': {}, 'toggle': {}})
            p2, _validation, _changes = apply_project_roots(
                p,
                {
                    'surface': surface,
                    'layers': layers,
                    'ui': ui,
                    'rules': rules,
                    'variables': variables,
                },
            )

            core.project = p2
            self._log("Project injected: GREEN base + RED toggle + 2 tick rules.")

            # Enable preview-engine blend tracing for this harness
            try:
                pe = getattr(core, 'preview_engine', None)
                if pe is not None:
                    setattr(pe, '_debug_blend_trace', True)
            except Exception:
                pass

            # IMPORTANT:
            # Preview renders from a Project *model* inside PreviewEngine, not directly
            # from CoreBridge.project (dict). After injection we must resync the
            # preview model, otherwise the preview can keep rendering a stale project.
            try:
                if hasattr(core, "rebuild_preview"):
                    core.rebuild_preview("harness_inject")
                elif hasattr(core, "sync_preview_engine_from_project_data"):
                    core.sync_preview_engine_from_project_data()
            except Exception:
                pass

            # Enable per-layer blend trace for this harness (captured during PreviewEngine.render_frame).
            try:
                pe = getattr(core, 'preview_engine', None)
                if pe is not None:
                    setattr(pe, '_debug_blend_trace', True)
            except Exception:
                pass

            # Ensure heartbeat is running
            try:
                self._toggle_heartbeat()
            except Exception:
                try:
                    self._start_heartbeat()
                except Exception:
                    pass

            self._log("Expected VISUAL: full strip alternates GREEN <-> RED at ~1Hz.")
            self._log("=== END HARNESS (setup) ===\n")

            def snap(tag: str) -> None:
                # Minimal snapshot to keep chat paste manageable.
                hb = 0
                try:
                    hb = int(getattr(self, '_hb_ticks', 0))
                except Exception:
                    pass

                core = getattr(self, 'app_core', None)

                # Rules status
                try:
                    fired = list(getattr(core, '_rules_last_fired_ids', []) or [])
                except Exception:
                    fired = []
                try:
                    errors_n = len(list(getattr(core, '_rules_last_errors', []) or []))
                except Exception:
                    errors_n = 0
                try:
                    last_eval = float(getattr(core, '_rules_last_eval_t', 0.0))
                except Exception:
                    last_eval = 0.0

                # Signals
                sq = None
                sqi = None
                try:
                    sb = getattr(core, 'signal_bus', None)
                    snap2 = sb.snapshot() if sb is not None and hasattr(sb, 'snapshot') else None
                    sigs = dict(getattr(snap2, 'signals', {}) or {}) if snap2 is not None else {}
                    sq = sigs.get('time.square1hz', None)
                    sqi = sigs.get('time.square1hz_inv', None)
                except Exception:
                    pass

                # Project + PreviewEngine layer state (only what we need)
                p_l0 = None
                p_l1 = None
                try:
                    pr = getattr(core, 'project', {}) or {}
                    ls = pr.get('layers') or []
                    if isinstance(ls, list) and len(ls) >= 2:
                        p_l0 = {'op': ls[0].get('opacity'), 'c': (ls[0].get('params') or {}).get('color')}
                        p_l1 = {'op': ls[1].get('opacity'), 'c': (ls[1].get('params') or {}).get('color')}
                        if isinstance(ls[1].get('params'), dict) and 'opacity' in ls[1]['params']:
                            p_l1['lop'] = ls[1]['params'].get('opacity')
                except Exception:
                    pass

                pe = None
                pe_l0 = None
                pe_l1 = None
                try:
                    pe = getattr(core, 'preview_engine', None)
                    pm = getattr(pe, 'project', None) if pe is not None else None
                    pls = list(getattr(pm, 'layers', []) or []) if pm is not None else []
                    if isinstance(pls, list) and len(pls) >= 2:
                        pe_l0 = {'op': getattr(pls[0], 'opacity', None)}
                        pe_l1 = {'op': getattr(pls[1], 'opacity', None)}
                except Exception:
                    pass

                # Frame sample (final buffer)
                sample = None
                uniq = None
                try:
                    frame = getattr(pe, '_last_frame', None) if pe is not None else None
                    if frame:
                        s = set(frame)
                        uniq = len(s)
                        sample = list(s)[:1]
                except Exception:
                    pass

                self._log(f"[H] {tag} hb={hb} sq={sq} sqi={sqi} last_eval={last_eval:.3f} fired={fired[-1:] if fired else []} err={errors_n}")
                self._log(f"[L] proj0={p_l0} proj1={p_l1} pe0={pe_l0} pe1={pe_l1} preview uniq={uniq} sample={sample}")

                # Blend trace: only layer0+layer1, first pixel.
                try:
                    tr = getattr(pe, '_debug_last_trace', None) if pe is not None else None
                    if isinstance(tr, list) and tr:
                        for row in tr:
                            li = row.get('li')
                            if li in (0, 1):
                                self._log(f"[BT] li={li} op={row.get('opacity')} p0={row.get('p0')} out0_before={row.get('out0_before')} out0_after={row.get('out0_after')}")
                except Exception:
                    pass

            QtCore.QTimer.singleShot(150, lambda: snap("t+0.15s"))
            QtCore.QTimer.singleShot(950, lambda: snap("t+0.95s"))
            QtCore.QTimer.singleShot(1750, lambda: snap("t+1.75s"))
            def _final():
                snap("t+2.55s")
                # Stop heartbeat + tracing so the console doesn't keep spamming.
                try:
                    pe = getattr(core, 'preview_engine', None)
                    if pe is not None:
                        setattr(pe, '_debug_blend_trace', False)
                except Exception:
                    pass
                try:
                    if getattr(self, '_hb_running', False):
                        self._toggle_heartbeat()
                except Exception:
                    pass
            QtCore.QTimer.singleShot(2550, _final)
