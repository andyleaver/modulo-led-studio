"""Legacy Tk full preview window (removed).

This stub exists only for backward compatibility so imports do not crash.
The Qt build does not provide the Tk full preview window.
"""

class FullPreviewWindow:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("FullPreviewWindow is not available in the Qt-only build.")
