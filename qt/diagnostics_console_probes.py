from __future__ import annotations

from qt.diagnostics_console_probe_ui import DiagnosticsConsoleProbeUiMixin
from qt.diagnostics_console_probe_reports import DiagnosticsConsoleProbeReportsMixin
from qt.diagnostics_console_probe_runtime import DiagnosticsConsoleProbeRuntimeMixin


class DiagnosticsConsoleProbeMixin(
    DiagnosticsConsoleProbeRuntimeMixin,
    DiagnosticsConsoleProbeReportsMixin,
    DiagnosticsConsoleProbeUiMixin,
):
    pass
