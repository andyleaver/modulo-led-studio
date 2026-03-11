from __future__ import annotations

try:
    from qt.qt_compat import QtWidgets  # type: ignore
except Exception:
    from qt.qt_compat import QtWidgets  # type: ignore

def install_mask_tools_ui(owner):
    """Install the mask tools UI entry point.

    The dedicated mask panels own the current UI, so this module remains a no-op
    import target for callers that expect the function to exist.
    """
    # The active mask UI lives in dedicated panels.
    return
