from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class PlaylistEntry:
    name: str
    duration_s: float

class PlaylistPlayer:
    """Preview-time playlist player.

    Swaps whole projects at entry boundaries.
    Call tick(tnow) from the preview loop; returns a project dict to apply or None.
    """

    def __init__(self):
        self.enabled: bool = False
        self.entries: List[PlaylistEntry] = []
        self._i: int = 0
        self._t_entry_start: float = 0.0
        self._last_tick_t: float = 0.0
        self._presets_by_name: Dict[str, Dict[str, Any]] = {}

    def configure(self, *, entries: List[Dict[str, Any]], presets: List[Dict[str, Any]]) -> None:
        self.entries = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            nm = str(e.get("name") or "").strip()
            try:
                dur = float(e.get("duration_s") or 0.0)
            except Exception:
                dur = 0.0
            if nm and dur > 0.0:
                self.entries.append(PlaylistEntry(nm, dur))
        self._presets_by_name = {}
        for p in presets:
            if not isinstance(p, dict):
                continue
            nm = str(p.get("name") or "").strip()
            proj = p.get("project")
            if nm and isinstance(proj, dict):
                self._presets_by_name[nm] = proj
        self._i = 0
        self._t_entry_start = 0.0

    def start(self, tnow: float) -> None:
        self.enabled = True
        self._t_entry_start = float(tnow)
        self._last_tick_t = float(tnow)

    def stop(self) -> None:
        self.enabled = False

    def current_entry(self) -> Optional[PlaylistEntry]:
        if not self.entries:
            return None
        if self._i < 0 or self._i >= len(self.entries):
            self._i = 0
        return self.entries[self._i]

    def _next(self, tnow: float) -> None:
        if not self.entries:
            self._i = 0
            self._t_entry_start = float(tnow)
            return
        self._i = (self._i + 1) % len(self.entries)
        self._t_entry_start = float(tnow)

    def tick(self, *, tnow: float) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        tnow = float(tnow)
        if tnow <= self._last_tick_t:
            return None
        self._last_tick_t = tnow

        cur = self.current_entry()
        if cur is None:
            return None
        if self._t_entry_start <= 0.0:
            self._t_entry_start = tnow
        if (tnow - self._t_entry_start) >= float(cur.duration_s):
            self._next(tnow)
            cur = self.current_entry()
            if cur is None:
                return None
            proj = self._presets_by_name.get(cur.name)
            if isinstance(proj, dict):
                return proj
        return None


