from .diagnostics_console_doors_execution import DiagnosticsConsoleDoorsExecutionMixin
from .diagnostics_console_doors_harness import DiagnosticsConsoleDoorsHarnessMixin


class DiagnosticsConsoleDoorsRunnerMixin(
    DiagnosticsConsoleDoorsHarnessMixin,
    DiagnosticsConsoleDoorsExecutionMixin,
):
    pass
