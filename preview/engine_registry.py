"""Preview engine registry (v1)

Holds a reference to the last constructed PreviewEngine so health probes
can report performance stats without UI access.
"""

from __future__ import annotations

from typing import Any, Optional

LAST_PREVIEW_ENGINE: Optional[Any] = None
