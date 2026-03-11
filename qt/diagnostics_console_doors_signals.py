from __future__ import annotations

import time
import json


class DiagnosticsConsoleDoorsSignalProbesMixin:
    def _probe_time_signals(self) -> str:
        """Door G1: Time signals are present and advance under diagnostics.

        Goals (audited, no roadmap):
        - Prove canonical derived time signals exist on the signal bus.
        - Prove they actually change when diagnostics drives time.

        Notes:
        - We do NOT require preview widgets to be rendering.
        - We drive CoreBridge._update_signals_from_preview(t) with wallclock-forced mode.
        - Relies on published timing signals: time.square1hz, time.square1hz_inv, time.phase1hz.
        """
        core = getattr(self, 'app_core', None)
        if core is None:
            return "[TimeSignals] ERROR: no app_core"

        ev: dict = {}
        old_force = bool(getattr(core, '_force_wallclock_signals', False))
        try:
            core._force_wallclock_signals = True

            base = float(int(time.time())) + 0.10
            # Step by 0.60s so we must cross the 0.5 phase boundary.
            ts = [base + (i * 0.60) for i in range(10)]

            sq = []
            inv = []
            phase = []
            t_seen = []

            for tt in ts:
                try:
                    core._update_signals_from_preview(float(tt))
                except Exception:
                    pass
                sig = getattr(core, 'signals', {}) or {}
                sq.append(sig.get('time.square1hz'))
                inv.append(sig.get('time.square1hz_inv'))
                phase.append(sig.get('time.phase1hz'))
                t_seen.append(sig.get('time.t') if 'time.t' in sig else None)

            ev["time_square1hz_samples"] = sq
            ev["time_square1hz_inv_samples"] = inv
            ev["time_phase1hz_samples"] = phase[:8] + (["..."] if len(phase) > 8 else [])
            ev["time_t_samples"] = t_seen[:6] + (["..."] if len(t_seen) > 6 else [])
            ev["keys_have_time_square1hz"] = any(v is not None for v in sq)
            ev["keys_have_time_square1hz_inv"] = any(v is not None for v in inv)
            ev["keys_have_time_phase1hz"] = any(v is not None for v in phase)
            ev["last_error"] = getattr(core, '_signal_bus_update_error', None)

            # Presence
            if not ev["keys_have_time_square1hz"] or not ev["keys_have_time_square1hz_inv"] or not ev["keys_have_time_phase1hz"]:
                return "[TimeSignals] FAIL: required time keys missing " + json.dumps(ev, separators=(',',':'))

            # Toggle proof: square should show both 0 and 1 when time advances across boundary.
            vals = set([float(v) for v in sq if v is not None])
            if 0.0 in vals and 1.0 in vals:
                return "[TimeSignals] PASS"

            return "[TimeSignals] FAIL: time.square1hz did not toggle " + json.dumps(ev, separators=(',',':'))

        finally:
            try:
                core._force_wallclock_signals = old_force
            except Exception:
                pass

    def _probe_audio_signals(self) -> str:
        """Door H1: Audio signals exist and vary over time in SIM mode.

        Goals (audited, no roadmap):
        - Prove canonical audio keys exist on the signal bus when AudioService is active.
        - Prove at least one value changes across time steps (i.e., not stuck at a constant).

        Notes:
        - This is a PREVIEW/SIM truth probe (export parity is a separate door).
        - We do not require a microphone; we rely on the deterministic AudioSim backend.
        """
        core = getattr(self, 'app_core', None)
        if core is None:
            return "[AudioSignals] ERROR: no app_core"

        ev: dict = {}
        # Drive audio/time via the same bridge path used by other probes.
        base = float(int(time.time())) + 0.10
        ts = [base + (i * 0.37) for i in range(14)]  # odd step to avoid repeating phases

        energy = []
        mono0 = []
        keys_present = {"audio.energy": False, "audio.mono0": False}

        try:
            # Ensure audio backend is stepped at least once.
            if hasattr(core, "audio_service") and hasattr(core.audio_service, "step"):
                core.audio_service.step(base)
        except Exception:
            pass

        prev_force = bool(getattr(core, "_force_wallclock_signals", False))
        try:
            setattr(core, "_force_wallclock_signals", True)
        except Exception:
            pass
        t_used = []

        for tt in ts:
            t_used.append(tt)
            # Ensure audio backend advances with time.
            try:
                if hasattr(core, "audio_service") and hasattr(core.audio_service, "step"):
                    core.audio_service.step(tt)
            except Exception:
                pass

            try:
                # This call is the canonical place where SignalBus gets updated.
                if hasattr(core, "_update_signals_from_preview"):
                    core._update_signals_from_preview(tt)
            except Exception:
                # Best-effort; keep collecting.
                pass

            sig = getattr(core, "signals", None)
            if not isinstance(sig, dict):
                sig = {}

            keys_present["audio.energy"] = keys_present["audio.energy"] or ("audio.energy" in sig)
            keys_present["audio.mono0"] = keys_present["audio.mono0"] or ("audio.mono0" in sig)

            e = sig.get("audio.energy", None)
            m0 = sig.get("audio.mono0", None)
            energy.append(float(e) if isinstance(e, (int, float)) else None)
            mono0.append(float(m0) if isinstance(m0, (int, float)) else None)


        try:
            setattr(core, "_force_wallclock_signals", prev_force)
        except Exception:
            pass

        ev["energy_samples"] = energy[:10] + (["..."] if len(energy) > 10 else [])
        ev["mono0_samples"] = mono0[:10] + (["..."] if len(mono0) > 10 else [])
        ev["t_used_samples"] = t_used[:10] + (["..."] if len(t_used) > 10 else [])
        ev["keys_have_audio_energy"] = bool(keys_present["audio.energy"])
        ev["keys_have_audio_mono0"] = bool(keys_present["audio.mono0"])
        ev["audio_backend"] = getattr(getattr(core, "audio_service", None), "backend_name", None)
        ev["audio_status"] = getattr(getattr(core, "audio_service", None), "status", None)
        ev["audio_last_error"] = getattr(getattr(core, "audio_service", None), "last_error", None)

        # Determine if audio is "alive": we need non-null samples and at least 2 distinct values.
        def _distinct(vals):
            vv = [v for v in vals if isinstance(v, (int, float))]
            return len(set([round(v, 6) for v in vv]))

        alive = (
            (ev["keys_have_audio_energy"] and _distinct(energy) >= 2)
            or (ev["keys_have_audio_mono0"] and _distinct(mono0) >= 2)
        )

        if alive:
            return "[AudioSignals] PASS"
        return "[AudioSignals] FAIL: audio signals did not vary/appear " + json.dumps(ev, separators=(',',':'))

