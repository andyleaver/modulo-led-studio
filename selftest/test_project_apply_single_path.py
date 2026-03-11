from __future__ import annotations

import inspect

from app import project_apply, project_canonical


def test_project_canonical_apply_wrappers_delegate_to_shared_apply_module():
    p = {"layers": [], "ui": {}, "surface": {"kind": "strip", "count": 8}}

    canonical_result = project_canonical.apply_project_root(p, "variables", {"speed": 1})
    shared_result = project_apply.apply_project_root(p, "variables", {"speed": 1})

    assert canonical_result == shared_result


def test_project_canonical_source_does_not_duplicate_apply_loop():
    src = inspect.getsource(project_canonical)
    assert "return _apply_project_roots(" in src
    assert "return _apply_project_root(" in src
    assert src.count("for key, value in dict(updates or {}).items()") == 0
