from __future__ import annotations


def project_manager_diag_exc(exc: Exception, where: str, details: dict | None = None) -> None:
    """Best-effort diagnostics reporting for project manager modules.

    Never recurse. Never raise.
    """
    try:
        from runtime.diagnostics import GLOBAL_DIAGS
        GLOBAL_DIAGS.exception(
            exc,
            domain="PROJECT",
            code="PROJECT_MANAGER_EXCEPTION",
            summary=f"project manager exception: {where}",
            details={"file": "app/project_manager.py", "where": where, **(details or {})},
        )
    except Exception:
        return
