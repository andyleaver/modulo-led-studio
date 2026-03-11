from __future__ import annotations

from qt.diagnostics_console_doors_runner import DiagnosticsConsoleDoorsRunnerMixin
from qt.diagnostics_console_full_audit import DiagnosticsConsoleFullAuditMixin
from qt.diagnostics_console_doors_signals import DiagnosticsConsoleDoorsSignalProbesMixin
from qt.diagnostics_console_doors_overrides import DiagnosticsConsoleDoorsOverrideProbesMixin
from qt.diagnostics_console_doors_resolver import DiagnosticsConsoleDoorsResolverProbeMixin
from qt.diagnostics_console_doors_utils import DiagnosticsConsoleDoorsUtilityMixin


class DiagnosticsConsoleDoorsMixin(
    DiagnosticsConsoleDoorsUtilityMixin,
    DiagnosticsConsoleDoorsSignalProbesMixin,
    DiagnosticsConsoleDoorsOverrideProbesMixin,
    DiagnosticsConsoleDoorsResolverProbeMixin,
    DiagnosticsConsoleDoorsRunnerMixin,
    DiagnosticsConsoleFullAuditMixin,
):
    """Composed Doors Open diagnostics mixin."""

    pass
