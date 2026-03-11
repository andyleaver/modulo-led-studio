from __future__ import annotations

import pytest

pytest.importorskip("qt.qt_compat")

from qt.diagnostics_tab_actions import DiagnosticsTabActionsMixin
from qt.diagnostics_tab_core import DiagnosticsTabCoreMixin


class _Buffer:
    def __init__(self) -> None:
        self.text = ""

    def setPlainText(self, text: str) -> None:
        self.text = str(text)

    def toPlainText(self) -> str:
        return self.text


class _Picker:
    def __init__(self, idx: int = 0) -> None:
        self._idx = idx

    def currentIndex(self) -> int:
        return self._idx


class _Owner(DiagnosticsTabCoreMixin, DiagnosticsTabActionsMixin):
    def __init__(self) -> None:
        self.probe_output = _Buffer()
        self.out = _Buffer()
        self.test_picker = _Picker(0)
        self.called = False
        self._test_specs = [("Probe", self._run_probe)]

    def _run_probe(self) -> None:
        self.called = True
        self._set_probe_text("probe result")


def test_run_selected_test_calls_probe_and_writes_result() -> None:
    owner = _Owner()
    owner._run_selected_test()
    assert owner.called is True
    assert owner.probe_output.toPlainText() == "probe result"
    assert owner.out.toPlainText() == "probe result"


def test_set_probe_text_mirrors_to_both_outputs() -> None:
    owner = _Owner()
    owner._set_probe_text("hello")
    assert owner.probe_output.toPlainText() == "hello"
    assert owner.out.toPlainText() == "hello"
