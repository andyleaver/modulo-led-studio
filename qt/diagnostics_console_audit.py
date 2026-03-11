from __future__ import annotations

from qt.diagnostics_console_audit_core import DiagnosticsConsoleAuditCoreMixin
from qt.diagnostics_console_audit_suites import DiagnosticsConsoleAuditSuitesMixin


class DiagnosticsConsoleAuditMixin(
    DiagnosticsConsoleAuditCoreMixin,
    DiagnosticsConsoleAuditSuitesMixin,
):
    """Composed audit diagnostics mixin."""

    pass
