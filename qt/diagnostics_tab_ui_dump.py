from __future__ import annotations


def dump_ui_layout_strip_preview(main_window=None) -> str:
    """Return a concise dump of strip/preview UI state for diagnostics."""
    try:
        from qt.wiretap import dump_ui_layout_strip_preview as dump_impl
        return dump_impl(main_window)
    except Exception as exc:
        return f"[dump_ui_layout_strip_preview] ERROR: {exc}"
