"""Headless core bridge for Qt.

Avoids creating a Tk root window when launching Qt.
Provides the minimal API expected by qt/qt_app.py.
"""

from __future__ import annotations

from pathlib import Path
import json

from app.json_sanitize import sanitize_for_json
import uuid

from app.project_manager import ProjectManager
from app.project_normalize import normalize_project_zones_masks_groups
from app.project_validation import validate_project
from runtime.signal_bus import SignalBus
from runtime.audio_service import AudioService
from runtime.variables import get_variables_state, ensure_variables
from runtime.rules_v6 import ensure_rules_v6, evaluate_rules_v6




def _ensure_layer_uids(proj: dict) -> None:
    """Ensure each layer dict has a stable uid field (used for preview state persistence)."""
    try:
        layers = proj.get("layers")
        if not isinstance(layers, list):
            return
        for ld in layers:
            if not isinstance(ld, dict):
                continue
            uid = ld.get("uid") or ld.get("__uid")
            if not isinstance(uid, str) or not uid.strip():
                uid = uuid.uuid4().hex
            ld["uid"] = uid
            ld["__uid"] = uid
    except Exception:
        return



def _ensure_default_strip60_in_project(p: dict) -> tuple[dict, bool]:
    """Ensure project has a concrete layout with strip+60 LEDs if missing/invalid (read/write project dict)."""
    try:
        p2 = dict(p or {})
        lay = dict(p2.get("layout") or {})
        shape = str(lay.get("shape") or "").strip().lower()
        num = lay.get("num_leds", None)
        try:
            num_i = int(num) if num is not None else 0
        except Exception:
            num_i = 0

        needs = False
        if shape not in ("strip", "cells"):
            needs = True
            shape = "strip"
        if num_i <= 0:
            needs = True
            num_i = 60

        if needs:
            lay["shape"] = shape
            lay["num_leds"] = num_i
            # keep other layout keys if present; if missing, seed safe defaults
            lay.setdefault("led_pin", 6)
            lay.setdefault("matrix_w", 16)
            lay.setdefault("matrix_h", 16)
            lay.setdefault("cell_size", 20)
            p2["layout"] = lay
            return p2, True
        return p2, False
    except Exception:
        return (p or {}), False


class CoreBridge:
    def __init__(self):
        self.pm = ProjectManager()
        self._project = {}  # backing store for project property
        self._project_rev = 0  # increments on every project set (UI sync guard)
        # Initialize backing project from ProjectManager if available
        try:
            if hasattr(self, 'pm') and self.pm is not None and hasattr(self.pm, 'get'):
                p0 = self.pm.get()
                if isinstance(p0, dict) and p0:
                    self._project = p0
                    # Phase A1 lock: normalize zones/groups/masks on startup load (idempotent)
                    try:
                        p2, _changes = normalize_project_zones_masks_groups(self._project)
                        if _changes:
                            self._project = p2
                            try:
                                if hasattr(self, 'pm') and self.pm is not None and hasattr(self.pm, 'set'):
                                    self.pm.set(p2)
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # Ensure layout exists in project dict so Diagnostics/Targeting/Export share truth.
                    try:
                        p3, changed3 = _ensure_default_strip60_in_project(self._project)
                        if changed3:
                            self._project = p3
                            try:
                                if hasattr(self, 'pm') and self.pm is not None and hasattr(self.pm, 'set'):
                                    self.pm.set(p3)
                            except Exception:
                                pass
                    except Exception:
                        pass


        except Exception:
            pass

        self._selection_indices: list[int] = []
        self._full_preview_engine = None
        self._full_preview_geom = None
        self._full_preview_audio = None
        self._export_target_id = "arduino_avr_fastled_msgeq7"

        # Phase 6.1: Signal Bus (time/audio) for inspection + future Rules.
        self.signal_bus = SignalBus()
        # Release R1: engine-owned always-on audio service
        self.audio_service = AudioService()
        # Back-compat: PreviewEngine expects an object with .step()/.state; we pass the backend.
        self._full_preview_audio = getattr(self.audio_service, "backend", None)
        self.preview_audio = self._full_preview_audio
        self.preview_audio_mode = getattr(self.audio_service, "mode", "sim")
        self.preview_audio_backend = getattr(self.audio_service, "backend_name", type(self._full_preview_audio).__name__ if self._full_preview_audio is not None else "AudioSim")
        self.preview_audio_status = getattr(self.audio_service, "status", "OK")
        self.preview_audio_last_error = getattr(self.audio_service, "last_error", "")
        self._signal_last_t = None  # type: float | None
        self._signal_frame = 0

        # Phase 6.2/6.3: Variables + Rules runtime state (kept runtime to avoid project churn).
        try:
            v0 = get_variables_state(self._project)
            self._variables_state = v0 if isinstance(v0, dict) else {"number": {}, "toggle": {}}
        except Exception:
            self._variables_state = {"number": {}, "toggle": {}}
        self._rules_v6_prev_state: dict = {}
        self._rules_v6_last_apply_t: float = 0.0

        # Ensure preview engine/geometry are ready on startup so the UI can render immediately.
        # (Some UI paths lazily rebuild, but blank startup makes diagnosis harder.)
        try:
            self._rebuild_full_preview_engine()
        except Exception:
            pass


    # ---- Phase 6.1: signal bus surface ----
    @property
    def preview_engine(self):
        """Live preview engine used by Qt preview widgets."""
        return self._full_preview_engine

    @property
    def project_data(self):
        """Alias for compatibility with older preview widgets."""
        return self.project

    def _update_signals_from_preview(self, t: float) -> None:
        """Update the signal bus from the preview's audio + current time.

        Called from UI render paths after PreviewEngine.render_frame() so audio
        state is already stepped.
        """
        try:
            tt = float(t)
        except Exception:
            tt = 0.0
        last = getattr(self, '_signal_last_t', None)
        try:
            dt = 0.0 if last is None else max(0.0, float(tt) - float(last))
        except Exception:
            dt = 0.0
        try:
            self._signal_last_t = tt
        except Exception:
            self._signal_last_t = None
        try:
            self._signal_frame = int(getattr(self, '_signal_frame', 0)) + 1
        except Exception:
            self._signal_frame = 1
        audio_state = None
        try:
            svc = getattr(self, "audio_service", None)
            if svc is not None:
                svc.step(tt)
                audio_state = getattr(svc, "state", None)
            else:
                a = getattr(self, '_full_preview_audio', None)
                if a is not None and hasattr(a, 'state'):
                    audio_state = getattr(a, 'state')
        except Exception:
            audio_state = None

        # Update signals first (time/audio + current variables runtime state)
        try:
            self.signal_bus.update(
                t=tt,
                dt=dt,
                frame=int(self._signal_frame),
                audio_state=audio_state,
                variables_state=getattr(self, "_variables_state", None),
            )
        except Exception:
            pass

        # Phase 6.3: Evaluate rules against the signal snapshot.
        try:
            p = self.project
            # Ensure schema exists (idempotent, no churn unless missing)
            p2, ch = ensure_rules_v6(p)
            if ch:
                try:
                    self.project = p2
                    p = self.project
                except Exception:
                    pass

            # Apply rules at a modest cadence to avoid UI churn.
            last_apply = float(getattr(self, "_rules_v6_last_apply_t", 0.0) or 0.0)
            if (tt - last_apply) >= 0.05:
                prev_state = getattr(self, "_rules_v6_prev_state", {})
                vstate = getattr(self, "_variables_state", {"number": {}, "toggle": {}})
                snap = self.signal_bus.snapshot()
                res = evaluate_rules_v6(
                    project=p,
                    signals=dict(snap.signals or {}),
                    variables_state=vstate,
                    prev_state=prev_state,
                    allow_layer_param_mutation=True,
                )
                # Remember last evaluation outcomes for UI inspection
                try:
                    self._rules_v6_last_fired_ids = list(res.fired_rule_ids or [])
                except Exception:
                    self._rules_v6_last_fired_ids = []
                try:
                    self._rules_v6_last_errors = list(res.errors or [])
                except Exception:
                    self._rules_v6_last_errors = []
                try:
                    self._rules_v6_last_eval_t = float(tt)
                except Exception:
                    self._rules_v6_last_eval_t = 0.0

                # Phase 6.5: Per-rule debug state for UI (safe/inspectable)
                try:
                    per = getattr(self, "_rules_v6_per_rule", None)
                    if not isinstance(per, dict):
                        per = {}
                    # Map errors by rule id (best-effort)
                    err_by: dict = {}
                    try:
                        for msg in list(res.errors or []):
                            s = str(msg)
                            # expected prefix: "rule <id>: ..."
                            if s.startswith("rule "):
                                parts = s.split(":", 1)
                                head = parts[0].strip()
                                rid2 = head.replace("rule", "").strip()
                                if rid2:
                                    err_by[rid2] = s
                    except Exception:
                        err_by = {}
                    # Build state snapshot for each rule in project
                    try:
                        rules0 = (p.get("rules_v6") or [])
                        rules_list2 = list(rules0) if isinstance(rules0, list) else []
                    except Exception:
                        rules_list2 = []
                    for rr0 in rules_list2:
                        rr = rr0 if isinstance(rr0, dict) else {}
                        rid2 = str(rr.get("id", "") or "")
                        if not rid2:
                            continue
                        d = per.get(rid2) if isinstance(per.get(rid2), dict) else {}
                        d = dict(d)
                        trig2 = str(rr.get("trigger", "tick") or "tick")
                        # Current trigger "state" as tracked in prev_state
                        st = None
                        try:
                            if trig2 == "rising":
                                st = bool(prev_state.get(f"rise:{rid2}", False))
                            elif trig2 == "threshold":
                                st = bool(prev_state.get(f"thr:{rid2}", False))
                            elif trig2 == "tick":
                                st = True
                        except Exception:
                            st = None
                        d["trigger"] = trig2
                        d["state"] = st
                        try:
                            d["cond_ok"] = bool(prev_state.get(f"cond:{rid2}", True))
                        except Exception:
                            d["cond_ok"] = True
                        d["enabled"] = bool(rr.get("enabled", True))
                        d["name"] = str(rr.get("name", "") or "")
                        d["last_eval_t"] = float(tt)
                        if rid2 in list(res.fired_rule_ids or []):
                            d["last_fire_t"] = float(tt)
                        if rid2 in err_by:
                            d["last_error"] = str(err_by[rid2])
                        else:
                            # Clear previous error once it stops happening
                            d.pop("last_error", None)
                        per[rid2] = d
                    self._rules_v6_per_rule = per
                except Exception:
                    pass
                # Update runtime variables state
                try:
                    self._variables_state = res.variables_state
                except Exception:
                    pass

                # Apply layer param mutations into project (rare, only when fired)
                try:
                    muts = res.project_mutations.get("layer_param") if isinstance(res.project_mutations, dict) else None
                except Exception:
                    muts = None
                if muts:
                    try:
                        pnow = self.project
                        layers = list((pnow.get("layers") or []))
                        changed = False
                        for (li, param, val) in list(muts):
                            # li == -1 means "active layer"
                            try:
                                if int(li) == -1:
                                    li = int((pnow.get("active_layer", 0) or 0))
                            except Exception:
                                pass
                            if li < 0 or li >= len(layers):
                                continue
                            L = dict(layers[li] or {})
                            params = dict(L.get("params") or {}) if isinstance(L.get("params"), dict) else {}
                            # best-effort numeric coercion
                            try:
                                params[str(param)] = float(val) if isinstance(val, (int, float)) else val
                            except Exception:
                                params[str(param)] = val
                            L["params"] = params
                            layers[li] = L
                            changed = True
                        if changed:
                            pnew = dict(pnow)
                            pnew["layers"] = layers
                            self.project = pnew
                    except Exception:
                        pass

                try:
                    self._rules_v6_last_apply_t = float(tt)
                except Exception:
                    self._rules_v6_last_apply_t = last_apply
        except Exception:
            pass


    def get_rules_v6_last_fired_summary(self) -> str:
        """Return a human-readable last-fired summary for Phase 6 rules."""
        try:
            ids = list(getattr(self, "_rules_v6_last_fired_ids", []) or [])
        except Exception:
            ids = []
        if not ids:
            return "Last fired: (none)"
        # Map ids -> names if possible
        try:
            p = self.project
            rules = list((p.get("rules_v6") or []))
            id_to_name = {}
            for r in rules:
                if isinstance(r, dict) and r.get("id"):
                    id_to_name[str(r.get("id"))] = str(r.get("name") or r.get("id"))
            parts = [id_to_name.get(str(i), str(i)) for i in ids]
        except Exception:
            parts = [str(i) for i in ids]
        return "Last fired: " + ", ".join(parts)

    def get_signal_snapshot(self) -> dict:
        """Return a dict snapshot of current signal values (best-effort)."""
        try:
            snap = self.signal_bus.snapshot()
            return dict(snap.signals or {})
        except Exception:
            return {}

    # ---- core project surface expected by qt_app.py ----
    # ---- core project surface expected by qt_app.py ----
    @property
    def project(self) -> dict:
        try:
            p = getattr(self, '_project', None)
            return p if isinstance(p, dict) else {}
        except Exception:
            return {}

    @property
    def last_validation(self):
        """Return last validation snapshot: {'ok': bool, 'errors': [...], 'warnings': [...]}"""
        try:
            return self._last_validation
        except Exception:
            return {'ok': True, 'errors': [], 'warnings': []}

    def project_revision(self) -> int:
        """Monotonic revision counter for UI panels to avoid redundant refresh."""
        try:
            return int(getattr(self, '_project_rev', 0))
        except Exception:
            return 0


    @project.setter
    def project(self, value):
        # Phase A1 lock: normalize + validate on every project set
        p = value if isinstance(value, dict) else {}
        try:
            p, _changes = normalize_project_zones_masks_groups(p)
        except Exception:
            _changes = []

        # Phase 6: ensure variables + rules schema exist (idempotent)
        try:
            p, _vchg = ensure_variables(p)
        except Exception:
            _vchg = False
        try:
            p, _rchg = ensure_rules_v6(p)
        except Exception:
            _rchg = False

        # Keep runtime variables state in sync with project writes (UI edits).
        try:
            v0 = get_variables_state(p)
            if isinstance(v0, dict):
                self._variables_state = v0
        except Exception:
            pass
        try:
            snap = validate_project(p)
            if not isinstance(snap, dict):
                snap = {'ok': True, 'errors': [], 'warnings': []}
        except Exception as e:
            snap = {'ok': False, 'errors': [f'validate_project failed: {e}'], 'warnings': []}
        self._last_validation = snap
        # Store
        self._project = p
        try:
            self._project_rev = int(getattr(self, '_project_rev', 0)) + 1
        except Exception:
            self._project_rev = 1
        # Persist if possible (guard against recursion)
        try:
            if hasattr(self, 'pm') and self.pm is not None and hasattr(self.pm, 'set'):
                self.pm.set(p)
        except Exception:
            pass
        # Keep preview and UI in sync with the updated project.
        # NOTE: In Modulo, the preview is the truth — any project mutation must be reflected immediately.
        try:
            self.rebuild_preview(reason="project.setter")
        except Exception:
            # Never crash on UI-side rebuilds; diagnostics will surface wiring issues.
            pass

    @property
    def target_mask(self) -> str | None:
        try:
            p = self.project or {}
            ui = p.get("ui") or {}
            if not isinstance(ui, dict):
                return None
            v = ui.get("target_mask")
            return str(v) if v is not None else None
        except Exception:
            return None

    @target_mask.setter
    def target_mask(self, key: str | None):
        try:
            p = self.project or {}
            ui0 = p.get("ui") or {}
            ui = dict(ui0) if isinstance(ui0, dict) else {}
            if key is None:
                ui.pop("target_mask", None)
            else:
                ui["target_mask"] = str(key)
            p2 = dict(p)
            p2["ui"] = ui
            self.project = p2
        except Exception:
            pass

    # ---- Phase A1: masks helpers (backend; UI-agnostic) ----
    def add_composed_mask(self, key: str, op: str, a, b) -> None:
        """Add a composed mask into the current project (copy-on-write)."""
        from app.masks_api import create_composed_mask

        p = self.project or {}
        n = None
        try:
            layout = (p or {}).get("layout") or {}
            if isinstance(layout, dict) and "count" in layout:
                n = int(layout.get("count") or 0) or None
        except Exception:
            n = None

        p2 = create_composed_mask(p, key, op, a, b, validate=True, n=n)
        self.project = p2

    # ---- export target ----
    def get_export_target_id(self) -> str:
        try:
            p = self.project or {}
            ex = p.get("export") or {}
            if isinstance(ex, dict):
                tid = ex.get("target_id")
                if tid:
                    return str(tid)
        except Exception:
            pass
        return str(self._export_target_id)

    def set_export_target_id(self, tid: str):
        try:
            self._export_target_id = str(tid)
        except Exception:
            pass

    # ---- selection ----
    def get_selection_indices(self) -> list[int]:
        try:
            return list(self._selection_indices or [])
        except Exception:
            return []

    def set_selection_indices(self, indices):
        try:
            out: list[int] = []
            for x in (indices or []):
                try:
                    out.append(int(x))
                except Exception:
                    pass
            self._selection_indices = sorted(set(out))
        except Exception:
            self._selection_indices = []

    # ---- preview ----
    def _rebuild_full_preview_engine(self):
        """Rebuild full preview renderer from current project (no Tk)."""
        try:
            from models.io import load_project
            from preview.preview_engine import PreviewEngine
            from preview.engine import build_strip_geom, build_cells_geom

            proj_dict = self.project or {}
            _ensure_layer_uids(proj_dict)

            # Preserve engine-owned state (stateful/game effects)
            prev_state_by_uid = {}
            try:
                prev_state_by_uid = dict(getattr(self._full_preview_engine, "_state_by_uid", {}) or {})
            except Exception:
                prev_state_by_uid = {}

            # NOTE: Project dicts are *intended* to be JSON, but UI/workflow code can
            # accidentally introduce cycles or non-JSON objects. We sanitize here so
            # preview never silently dies.
            clean_proj, sanitize_issues = sanitize_for_json(proj_dict)
            self._full_preview_sanitize_issues = sanitize_issues

            tmp = Path(self.pm.root_dir) / "out" / "_tmp_full_preview_project.json"
            tmp.parent.mkdir(exist_ok=True)
            tmp.write_text(json.dumps(clean_proj, indent=2), encoding="utf-8")

            project_model = load_project(tmp)
            # Release R1: reuse engine-owned audio backend (always-on)
            try:
                self._full_preview_audio = getattr(getattr(self, "audio_service", None), "backend", None)
            except Exception:
                self._full_preview_audio = None
            # Prime once so startup health can show non-zero values even before first render tick.
            try:
                if getattr(self, "audio_service", None) is not None:
                    self.audio_service.step(0.0)
            except Exception:
                pass
            # Expose audio to diagnostics/health-check
            self.preview_audio = self._full_preview_audio
            try:
                audio_cfg = (clean_proj.get('audio') or {}) if isinstance(clean_proj, dict) else {}
                self.preview_audio_mode = str(audio_cfg.get('mode') or getattr(getattr(self, "audio_service", None), "mode", "sim") or 'sim')
            except Exception:
                self.preview_audio_mode = getattr(getattr(self, "audio_service", None), "mode", "sim") or 'sim'
            self.preview_audio_backend = type(self._full_preview_audio).__name__ if self._full_preview_audio is not None else 'AudioSim'
            self.preview_audio_status = getattr(getattr(self, "audio_service", None), "status", "OK") or 'OK'
            self._full_preview_engine = PreviewEngine(
                project_model,
                self._full_preview_audio,
                signal_bus=getattr(self, 'signal_bus', None),
            )

            # Snapshot audio state for the startup health-check report.
            self._diagnostics_tick_audio()
            # Also publish an initial signals snapshot.
            # Seed the SignalBus with an initial snapshot so diagnostics/health panels
            # can display audio.* immediately on startup.
            # NOTE: SignalBus.update() is keyword-only.
            try:
                self.signal_bus.update(
                    t=0.0,
                    dt=0.0,
                    frame=0,
                    audio_state=getattr(self._full_preview_audio, 'state', None),
                    variables_state=None,
                )
            except Exception:
                pass

            # Apply persisted target mask to engine
            try:
                tm = self.target_mask
                setattr(self._full_preview_engine, "target_mask", tm)
            except Exception:
                pass

            try:
                if prev_state_by_uid:
                    self._full_preview_engine._state_by_uid.update(prev_state_by_uid)
            except Exception:
                pass

            lay = project_model.layout
            layout_dict = (clean_proj.get("layout") or {}) if isinstance(clean_proj, dict) else {}

            if getattr(lay, "shape", "strip") == "cells":
                mw = int(getattr(lay, "mw", 16) or 16)
                mh = int(getattr(lay, "mh", 16) or 16)
                cell = float(getattr(lay, "cell", 20) or 20)
                self._full_preview_geom = build_cells_geom(
                    mw, mh, cell,
                    serpentine=bool(layout_dict.get("serpentine", True)),
                    flip_x=bool(layout_dict.get("flip_x", False)),
                    flip_y=bool(layout_dict.get("flip_y", False)),
                    rotate=int(layout_dict.get("rotate", 0) or 0),
                )
            else:
                n = int(getattr(lay, "num_leds", 144) or 144)
                self._full_preview_geom = build_strip_geom(n)
        except Exception as e:
            # Persist the failure so diagnostics can explain *why* preview is blank.
            try:
                import traceback as _tb
                self._full_preview_last_error = f"{type(e).__name__}: {e}"
                self._full_preview_last_trace = "".join(_tb.format_exc())
            except Exception:
                self._full_preview_last_error = "(unknown preview rebuild error)"
                self._full_preview_last_trace = ""
            self._full_preview_engine = None
            self._full_preview_geom = None
            return
        # Last project validation snapshot (Phase A1 lock)
        self._last_validation = {'ok': True, 'errors': [], 'warnings': []}


    def sync_preview_engine_from_project_data(self) -> None:
        """Rebuild PreviewEngine.project from current project_data.

        Contract:
          - UI edits mutate CoreBridge.project (dict).
          - PreviewEngine renders from PreviewEngine.project (models.Project).
          - This function is the single supported bridge between the two.
        """
        if not getattr(self, "preview_engine", None):
            return
        if not getattr(self, "project", None):
            return
        try:
            import json, os, tempfile
            from models.io import load_project
            # Write to a temp file to reuse the canonical loader (migrations + schema handling).
            fd, tmp = tempfile.mkstemp(prefix="modulo_pd_", suffix=".json")
            os.close(fd)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.project, f, indent=2)
            proj_obj = load_project(tmp)
            try:
                os.remove(tmp)
            except Exception:
                pass
            # Swap the project object used by the renderer.
            self.preview_engine.project = proj_obj
            # Optional: keep a reference for diagnostics.
            self.preview_engine.project_data = self.project
        except Exception as e:
            # Never crash UI for a preview sync; record for health report.
            try:
                self._preview_sync_last_error = repr(e)
            except Exception:
                pass
    def _diagnostics_tick_audio(self):
        """Advance AudioSim slightly so health reports show non-zero values."""
        a = getattr(self, "preview_audio", None)
        if a is None:
            return
        if a.__class__.__name__ != "AudioSim":
            return
        for _ in range(10):
            a.step(0.05)


    def rebuild_preview(self, reason: str = "project_mutated") -> None:
        """Public, UI-safe preview refresh.

        UI panels mutate `project_data` in-place (toggle layer enabled,
        delete a layer, change effect, etc.). The PreviewEngine holds an
        internal normalized Project object, so we must explicitly sync the
        engine from the authoritative project dict after any mutation.

        This method is intentionally lightweight: it does not rebuild the
        entire engine unless required; it pushes updated project data into
        the engine and requests a redraw on any attached preview widgets.
        """
        try:
            self.sync_preview_engine_from_project_data()
        except Exception as e:
            self._last_error = f"rebuild_preview: {e!r}"

        # Nudge any preview widgets (strip/matrix) if present.
        for attr in ("preview_widget", "matrix_widget", "strip_preview_widget", "matrix_preview_widget"):
            try:
                w = getattr(self, attr, None)
                if w is not None and hasattr(w, "update"):
                    w.update()
            except Exception:
                pass