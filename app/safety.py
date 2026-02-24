from __future__ import annotations

"""Central safety wiring (NO duplicate validation logic).

This module only *orchestrates* existing checks so they run consistently.
It intentionally does NOT re-implement any validators.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class SafetyIssue:
    level: str  # "WARN" | "FAIL"
    area: str   # "targets" | "preview" | "export"
    message: str


def _health_dir() -> Path:
    root = Path(__file__).resolve().parents[1]
    out = root / "out" / "health_reports"
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_report(*, title: str, issues: List[SafetyIssue]) -> Path:
    import datetime

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    p = _health_dir() / f"health_{ts}.txt"
    lines: List[str] = []
    lines.append(title)
    lines.append("=" * max(10, len(title)))
    if not issues:
        lines.append("OK")
    else:
        for i in issues:
            lines.append(f"{i.level}: {i.area}: {i.message}")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def check_targets(*, target_id: Optional[str] = None) -> List[SafetyIssue]:
    """Run existing target pack validation.

    If target_id is provided, only return issues that match that id.
    """
    issues: List[SafetyIssue] = []
    try:
        from export.targets.registry import validate_targets

        problems = validate_targets()  # existing logic
        for item in (problems or []):
            tid = str(item.get("id") or "")
            if target_id and tid != target_id:
                continue
            err = str(item.get("error") or "Unknown error")
            issues.append(SafetyIssue("FAIL", "targets", f"{tid}: {err}"))
    except Exception as e:
        issues.append(SafetyIssue("FAIL", "targets", f"Target validation crashed: {e}"))
    return issues


def startup_smoke_check(app) -> List[SafetyIssue]:
    """Attempt a minimal preview rebuild using existing app method."""
    issues: List[SafetyIssue] = []
    try:
        # This method is the same one PreviewPanel uses; we just call it once
        # so failures are reported instead of silently degrading.
        if hasattr(app, "_rebuild_full_preview_engine"):
            app._rebuild_full_preview_engine()
        else:
            issues.append(SafetyIssue("FAIL", "preview", "Missing _rebuild_full_preview_engine()"))
    except Exception as e:
        issues.append(SafetyIssue("FAIL", "preview", f"Preview rebuild failed: {e}"))
    return issues


def run_startup_checks(app) -> tuple[List[SafetyIssue], Path]:
    """Run non-blocking startup checks and write a report."""
    issues: List[SafetyIssue] = []
    issues.extend(check_targets())
    issues.extend(startup_smoke_check(app))
    report = write_report(title="Modulo Safety Startup Check", issues=issues)
    return issues, report


def run_preexport_checks(*, target_id: str) -> tuple[List[SafetyIssue], Path]:
    """Run checks that should block export when FAIL."""
    issues = check_targets(target_id=target_id)
    report = write_report(title=f"Modulo Safety Pre-Export Check ({target_id})", issues=issues)
    return issues, report


import os
import time
from pathlib import Path

def _write_health_report(text: str) -> str:
    out_dir = Path("out") / "health_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    p = out_dir / f"health_{ts}.txt"
    p.write_text(text, encoding="utf-8")
    return str(p)

def run_health_check(app=None, startup: bool = True):
    """Run existing checks and write a report. Returns (SafetyReport, report_path)."""
    # Reuse the existing run_startup_checks if it exists; otherwise fall back to minimal.
    rep = None
    if "run_startup_checks" in globals():
        rep = run_startup_checks(app=app)
    else:
        # Minimal: validate targets only
        from export.targets.registry import validate_targets
        problems = validate_targets()
        from dataclasses import dataclass
        @dataclass
        class _Issue:
            level: str
            area: str
            message: str
        @dataclass
        class _Rep:
            issues: list
            @property
            def ok(self): return not any(i.level=="FAIL" for i in self.issues)
        issues=[]
        if problems:
            issues.append(_Issue("WARN","targets",f"{len(problems)} target issue(s)"))
        rep=_Rep(issues)

    # Build report text
    lines = []
    lines.append("Modulo Health Report")
    lines.append(f"Mode: {'startup' if startup else 'manual'}")
    lines.append("")
    if hasattr(rep, "issues"):
        if not rep.issues:
            lines.append("OK: no issues detected.")
        else:
            for i in rep.issues:
                lines.append(f"{i.level}: {i.area}: {i.message}")
    report_path = _write_health_report("\n".join(lines) + "\n")
    return rep, report_path
