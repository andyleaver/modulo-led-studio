from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class SafetyIssue:
    level: str
    area: str
    message: str


@dataclass
class SafetyReport:
    issues: List[SafetyIssue]

    @property
    def ok(self) -> bool:
        return not any(issue.level == 'FAIL' for issue in self.issues)


def _artifact_root() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    artifact_root = repo_root.parent / 'artifacts'
    artifact_root.mkdir(parents=True, exist_ok=True)
    return artifact_root


def _health_dir() -> Path:
    path = _artifact_root() / 'health_reports'
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_report(*, title: str, issues: List[SafetyIssue]) -> Path:
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')
    report_path = _health_dir() / f'health_{ts}.txt'
    lines: List[str] = [title, '=' * max(10, len(title))]
    if not issues:
        lines.append('OK')
    else:
        for issue in issues:
            lines.append(f'{issue.level}: {issue.area}: {issue.message}')
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return report_path


def check_targets(*, target_id: Optional[str] = None) -> List[SafetyIssue]:
    issues: List[SafetyIssue] = []
    try:
        from export.targets.registry import validate_targets

        for item in validate_targets() or []:
            tid = str(item.get('id') or '')
            if target_id and tid != target_id:
                continue
            err = str(item.get('error') or 'Unknown error')
            issues.append(SafetyIssue('FAIL', 'targets', f'{tid}: {err}'))
    except Exception as exc:
        issues.append(SafetyIssue('FAIL', 'targets', f'Target validation crashed: {exc}'))
    return issues


def startup_smoke_check(app) -> List[SafetyIssue]:
    issues: List[SafetyIssue] = []
    try:
        if hasattr(app, '_rebuild_full_preview_engine'):
            app._rebuild_full_preview_engine()
        else:
            issues.append(SafetyIssue('FAIL', 'preview', 'Missing _rebuild_full_preview_engine()'))
    except Exception as exc:
        issues.append(SafetyIssue('FAIL', 'preview', f'Preview rebuild failed: {exc}'))
    return issues


def run_startup_checks(app) -> Tuple[List[SafetyIssue], Path]:
    issues: List[SafetyIssue] = []
    issues.extend(check_targets())
    issues.extend(startup_smoke_check(app))
    return issues, write_report(title='Modulo Safety Startup Check', issues=issues)


def run_preexport_checks(*, target_id: str) -> Tuple[List[SafetyIssue], Path]:
    issues = check_targets(target_id=target_id)
    return issues, write_report(title=f'Modulo Safety Pre-Export Check ({target_id})', issues=issues)


def _run_tool(tool_relpath: str) -> tuple[bool, str]:
    import subprocess
    import sys

    tool = (Path(__file__).resolve().parents[1] / tool_relpath).resolve()
    if not tool.exists():
        return False, f'missing tool: {tool_relpath}'
    try:
        cp = subprocess.run([sys.executable, str(tool)], capture_output=True, text=True, timeout=20, check=False)
    except Exception as exc:
        return False, f'tool exception: {tool_relpath} :: {exc}'
    if cp.returncode != 0:
        msg = (cp.stdout + '\n' + cp.stderr).strip()
        return False, f'tool failed: {tool_relpath} rc={cp.returncode} :: {msg[:500]}'
    return True, cp.stdout.strip() or f'ok: {tool_relpath}'


def ensure_audit_docs(report: dict) -> None:
    ok_cm, msg_cm = _run_tool('tools/codemap_audit.py')
    ok_inv, msg_inv = _run_tool('tools/export_inventory_audit.py')
    report.setdefault('audits', {})
    report['audits']['codemap'] = {'ok': ok_cm, 'message': msg_cm}
    report['audits']['export_inventory'] = {'ok': ok_inv, 'message': msg_inv}


def run_health_check(app=None, startup: bool = True):
    issues, _ = run_startup_checks(app=app) if startup else (check_targets(), None)
    report = SafetyReport(issues=issues)

    payload = {
        'mode': 'startup' if startup else 'manual',
        'issues': [{'level': i.level, 'area': i.area, 'message': i.message} for i in report.issues],
    }
    try:
        ensure_audit_docs(payload)
    except Exception as exc:
        payload.setdefault('audits', {})
        payload['audits']['_exception'] = {'ok': False, 'message': str(exc)}

    lines = ['Modulo Health Report', f"Mode: {payload['mode']}", '']
    if payload['issues']:
        for item in payload['issues']:
            lines.append(f"{item['level']}: {item['area']}: {item['message']}")
    else:
        lines.append('OK: no issues detected.')

    audits = payload.get('audits') or {}
    if audits:
        lines.extend(['', '== Audited Indices =='])
        for key, value in audits.items():
            if not isinstance(value, dict):
                continue
            status = 'OK' if value.get('ok') else 'WARN'
            lines.append(f"{status}: {key}: {value.get('message', '')}")

    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')
    report_path = _health_dir() / f'health_{ts}.txt'
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return report, str(report_path)
