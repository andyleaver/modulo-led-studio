from __future__ import annotations

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


class DiagnosticsTabActionsMixin:
    def _run_quick_health_bundle(self):
        parts = []
        try:
            parts.append("Quick Health Check")
            parts.append("===================")
            parts.append("")
            parts.append("[1] Full Health Check")
            try:
                from app.project_diagnostics import run_full_health_check

                proj = self._project_data()
                report = run_full_health_check(
                    proj,
                    app_core=getattr(self, "app_core", None),
                    controller=getattr(self, "controller", None),
                )
                parts.append(str(report))
            except Exception:
                parts.append("Health check unavailable.\n" + traceback.format_exc())

            parts.append("")
            parts.append("[2] Resolver Inspector")
            try:
                self._dump_resolver_inspector()
                ri = getattr(self, "probe_output", None)
                txt = str(ri.toPlainText() or "") if ri is not None else ""
                if txt:
                    parts.append(txt[:6000])
                else:
                    parts.append("Resolver inspector produced no visible output.")
            except Exception:
                parts.append("Resolver inspector unavailable.\n" + traceback.format_exc())

            parts.append("")
            parts.append("[3] Preview / Export Parity")
            try:
                from app.composition_parity_probe import run_probe

                bid = str(getattr(self.app_core, "app_id", "") or "")
                res = run_probe(app_id=bid, diagnostics=_DIAGS)
                parts.append(_pretty(res))
            except Exception:
                parts.append("Composition parity probe unavailable.\n" + traceback.format_exc())

            self._set_probe_text("\n".join(parts))
        except Exception:
            self._set_probe_text("Quick health bundle failed.\n" + traceback.format_exc())

    def _run_selected_test(self):
        try:
            idx = int(self.test_picker.currentIndex())
            if idx < 0 or idx >= len(self._test_specs):
                return
            label, fn = self._test_specs[idx]
            self._diag_set(f"Running: {label}\n")
            fn()
        except Exception:
            self._set_probe_text(traceback.format_exc())

    def _copy(self):
        try:
            QtWidgets.QApplication.clipboard().setText(self.out.toPlainText())
        except Exception as e:
            _diag_exc(e, "qt/diagnostics_tab.py")
