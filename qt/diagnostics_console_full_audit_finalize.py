from __future__ import annotations

import json
import time
from pathlib import Path


def _artifact_run_dir(name: str) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    out_dir = repo_root.parent / "artifacts" / "diagnostics_runs" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


class DiagnosticsConsoleFullAuditFinalizeMixin:
    def _run_full_audit_headless(self) -> None:
        # Same audit, but safe to run repeatedly (runs inside clean sandbox).
        return self._run_full_audit()

    def _finalize_audit(self, report: dict, started: float) -> None:
        report["duration_s"] = round(time.time() - started, 3)

        # Compatibility aliases (some external scripts/tools expect these keys)
        # Ensure they are always present in the persisted report.
        report.setdefault("fail_step", None)
        report.setdefault("fail_summary", None)
        report.setdefault("evidence", {})
        first_fail = report.get("first_fail") or None
        if report.get("overall") == "FAIL" and first_fail:
            ff_id = first_fail.get("id")
            ff_summary = first_fail.get("summary")
            report["fail_step"] = ff_id
            report["fail_summary"] = ff_summary
            # Find the matching step details to persist as evidence.
            ev = {}
            try:
                for s in report.get("steps", []):
                    if s.get("id") == ff_id:
                        ev = s.get("details", {}) or {}
                        break
            except Exception:
                ev = {}
            report["evidence"] = ev

        # Persist report
        try:
            import json
            out_dir = _artifact_run_dir(report["id"])
            p = out_dir / "report.json"
            p.write_text(json.dumps(report, indent=2, sort_keys=False), encoding="utf-8")
            report_path = str(p)
        except Exception as e:
            report_path = None
            self._log(f"[Audit] Failed to write report: {e}")

        # Update UI summary
        overall = report.get("overall", "UNKNOWN")
        title = str(report.get("title") or "FULL AUDIT")
        first_fail = report.get("first_fail")
        if overall == "PASS":
            summary = f"{title}: PASS  ({report.get('duration_s')}s)"
        elif first_fail:
            summary = f"{title}: FAIL at {first_fail.get('id')} — {first_fail.get('summary')}"
        else:
            summary = f"{title}: {overall}"

        self._log("")
        self._log(f"[Audit] {summary}")
        if report_path:
            self._log(f"[Audit] Report saved: {report_path}")

        try:
            self.lbl_audit_summary.setText(summary + (f"\nReport: {report_path}" if report_path else ""))
            # show compact step list in details pane
            lines = []
            for s in report.get("steps", []):
                lines.append(f"{s['status']}: {s['id']} — {s['summary']}")
            if first_fail:
                # include evidence snippet
                ff_id = first_fail.get("id")
                for s in report.get("steps", []):
                    if s.get("id") == ff_id:
                        det = s.get("details", {})
                        if det:
                            lines.append("\n--- Evidence (first fail) ---")
                            try:
                                lines.append(json.dumps(det, indent=2)[:12000])
                            except Exception:
                                lines.append(str(det)[:12000])
                        break
            self.txt_audit_details.setPlainText("\n".join(lines))
            # guided label points to the first failing door
            if overall == "PASS":
                self.lbl_next.setText("All Doors Open: FULL AUDIT PASS. If something feels wrong, re-run FULL AUDIT to pinpoint the first divergence.")
            else:
                self.lbl_next.setText(summary)
        except Exception:
            pass

    # --- internal audit helpers (return ok, details) ---

