from __future__ import annotations

from qt.diagnostics_console_doors_overrides import DiagnosticsConsoleDoorsOverrideProbesMixin
from qt.diagnostics_console_doors_signals import DiagnosticsConsoleDoorsSignalProbesMixin
from qt.diagnostics_console_doors_resolver import DiagnosticsConsoleDoorsResolverProbeMixin


class DiagnosticsConsoleDoorsProbeMixin(
    DiagnosticsConsoleDoorsResolverProbeMixin,
    DiagnosticsConsoleDoorsSignalProbesMixin,
    DiagnosticsConsoleDoorsOverrideProbesMixin,
):
    pass
