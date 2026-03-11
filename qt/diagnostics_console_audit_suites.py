from .diagnostics_console_audit_composition import DiagnosticsConsoleAuditCompositionMixin
from .diagnostics_console_audit_coupled import DiagnosticsConsoleAuditCoupledMixin


class DiagnosticsConsoleAuditSuitesMixin(
    DiagnosticsConsoleAuditCompositionMixin,
    DiagnosticsConsoleAuditCoupledMixin,
):
    pass
