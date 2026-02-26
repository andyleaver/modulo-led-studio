"""Preview package.

Qt-only build: the legacy Tk full preview window is removed.
This package still provides headless/engine components used by Qt.
"""

# Keep compatibility symbol if someone imports it, but don't hard-fail.
try:
    from .full_preview import FullPreviewWindow  # type: ignore
except Exception:
    FullPreviewWindow = None  # type: ignore
