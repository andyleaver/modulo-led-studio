from __future__ import annotations


class CoreBridgePlaylistMixin:
    def configure_playlist(self, entries: list[dict]) -> None:
        """Configure playlist entries (list of {name,duration_s})."""
        try:
            self._playlist_entries = list(entries or [])
            pl = getattr(self, "_playlist_player", None)
            if pl is None:
                return
            from app.presets_store import load_presets
            presets = load_presets()
            pl.configure(entries=self._playlist_entries, presets=presets)
        except Exception as e:
            try:
                from runtime.diagnostics import GLOBAL_DIAGS
                GLOBAL_DIAGS.exception(e, domain="RUNTIME", code="PLAYLIST_CONFIG_FAIL", summary="Failed to configure playlist")
            except Exception:
                pass

    def start_playlist(self) -> None:
        try:
            import time as _time
            pl = getattr(self, "_playlist_player", None)
            if pl is None:
                return
            # Refresh preset mapping.
            self.configure_playlist(getattr(self, "_playlist_entries", []) or [])
            pl.start(_time.time())
            self._playlist_enabled = True
        except Exception as e:
            try:
                from runtime.diagnostics import GLOBAL_DIAGS
                GLOBAL_DIAGS.exception(e, domain="RUNTIME", code="PLAYLIST_START_FAIL", summary="Failed to start playlist")
            except Exception:
                pass

    def stop_playlist(self) -> None:
        try:
            pl = getattr(self, "_playlist_player", None)
            if pl is None:
                return
            pl.stop()
            self._playlist_enabled = False
        except Exception:
            pass

    def playlist_tick(self, tnow: float) -> None:
        """Advance playlist and apply project swap if needed."""
        try:
            if not bool(getattr(self, "_playlist_enabled", False)):
                return
            pl = getattr(self, "_playlist_player", None)
            if pl is None:
                return
            proj = pl.tick(tnow=float(tnow))
            if isinstance(proj, dict):
                self.project = proj
        except Exception as e:
            try:
                from runtime.diagnostics import GLOBAL_DIAGS
                GLOBAL_DIAGS.exception(e, domain="RUNTIME", code="PLAYLIST_TICK_FAIL", summary="Playlist tick failed")
            except Exception:
                pass
