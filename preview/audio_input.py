from __future__ import annotations
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

from .audio import AudioSim
from .audio_recorder import AudioRecorder

def _clamp01(x: float) -> float:
    if x < 0.0: return 0.0
    if x > 1.0: return 1.0
    return x

@dataclass
class ExternalAudioStatus:
    connected: bool = False
    last_error: str = ""
    last_update_ts: float = 0.0
    last_line: str = ""

class AudioInput:
    """Audio source abstraction for preview.

    Modes:
      - sim: internal AudioSim
      - external: serial feed (line-based protocol)
      - playback: AudioRecorder playback

    Protocols supported for external/inject:
      1) key=value pairs separated by spaces/commas/semicolons
         energy=0.5 mono0=0.1 ... l0=0.2 r0=0.3
      2) JSON object per line:
         {"energy":0.5,"mono0":0.1,"l0":0.2,"r0":0.3}
    """

    def __init__(self):
        self.sim = AudioSim()
        self.recorder = AudioRecorder()

        self.mode: str = "sim"
        self.gain: float = 1.0
        self.smoothing: float = 0.20  # 0..1

        self.state: Dict[str, float] = dict(self.sim.state)
        self.status = ExternalAudioStatus()

        self._stop_evt = threading.Event()
        self._thr: Optional[threading.Thread] = None
        self._serial = None
        self._port: str = ""
        self._baud: int = 115200

    def available_sources(self):
        return sorted(list(self.state.keys())) if self.state else ["energy"]

    # --- primary tick ---
    def step(self, t: float):
        if self.mode == "playback":
            st = self.recorder.sample()
            if isinstance(st, dict):
                self.state = self._apply_gain_smooth(st)
            return

        if self.mode == "sim":
            self.sim.step(t)
            self.state = self._apply_gain_smooth(dict(self.sim.state))
            try:
                self.recorder.add_frame(self.state)
            except Exception:
                pass
            return

        # external mode: reader thread updates state asynchronously
        return

    # --- gain/smoothing ---
    def _apply_gain_smooth(self, new_state: Dict[str, float]) -> Dict[str, float]:
        g = float(self.gain or 1.0)
        a = float(self.smoothing or 0.0)
        if a < 0.0: a = 0.0
        if a > 0.95: a = 0.95
        out = dict(self.state or {})
        for k, v in (new_state or {}).items():
            try:
                fv = float(v) * g
            except Exception:
                continue
            fv = _clamp01(fv)
            prev = float(out.get(k, 0.0) or 0.0)
            out[k] = (prev * a) + (fv * (1.0 - a))
        return out

    # --- external serial ---
    def connect(self, port: str, baud: int = 115200) -> bool:
        self.disconnect()
        self._port = str(port).strip()
        self._baud = int(baud)
        if not self._port:
            self.status = ExternalAudioStatus(False, "No port specified")
            return False
        try:
            import serial  # type: ignore
        except Exception as e:
            self.status = ExternalAudioStatus(False, "pyserial not installed: " + str(e))
            return False
        try:
            self._serial = serial.Serial(self._port, self._baud, timeout=0.2)
        except Exception as e:
            self.status = ExternalAudioStatus(False, "Open failed: " + str(e))
            return False

        self._stop_evt.clear()
        self._thr = threading.Thread(target=self._reader_loop, daemon=True)
        self._thr.start()
        self.status.connected = True
        self.status.last_error = ""
        return True

    def disconnect(self):
        self._stop_evt.set()
        try:
            if self._thr and self._thr.is_alive():
                self._thr.join(timeout=0.5)
        except Exception:
            pass
        self._thr = None
        try:
            if self._serial:
                self._serial.close()
        except Exception:
            pass
        self._serial = None
        self.status.connected = False

    def _reader_loop(self):
        if not self.state:
            self.state = dict(self.sim.state)
        while not self._stop_evt.is_set():
            try:
                line = self._serial.readline() if self._serial else b""
                if not line:
                    continue
                try:
                    s = line.decode("utf-8", errors="ignore").strip()
                except Exception:
                    continue
                if not s:
                    continue
                self.status.last_line = s[:200]
                self._apply_line(s)
                self.status.last_update_ts = time.time()
            except Exception as e:
                self.status.last_error = str(e)
                time.sleep(0.1)

    def inject_line(self, s: str):
        """Inject a protocol line (for debugging without serial)."""
        try:
            self.status.last_line = (s or "")[:200]
            self._apply_line(str(s))
            self.status.last_update_ts = time.time()
        except Exception as e:
            self.status.last_error = str(e)

    def _apply_line(self, s: str):
        s2 = (s or "").strip()
        if not s2:
            return

        # JSON object frame
        if s2.startswith("{") and s2.endswith("}"):
            try:
                import json
                obj = json.loads(s2)
                if isinstance(obj, dict):
                    updated = False
                    for k, v in obj.items():
                        k2 = str(k).lower().strip()
                        try:
                            fv = float(v)
                        except Exception:
                            continue
                        if k2.startswith("mono") or k2.startswith("l") or k2.startswith("r") or k2 == "energy":
                            self.state[k2] = _clamp01(fv)
                            updated = True
                    if updated and "energy" not in self.state:
                        e = 0.0
                        for i in range(7):
                            e += float(self.state.get(f"mono{i}", 0.0))
                        self.state["energy"] = _clamp01(e / 7.0)
                    if updated:
                        self.state = self._apply_gain_smooth(dict(self.state))
                        try:
                            self.recorder.add_frame(self.state)
                        except Exception:
                            pass
                    return
            except Exception:
                # fall through to key=value parsing
                pass

        # key=value parsing
        toks = []
        for part in s2.replace(",", " ").replace(";", " ").split():
            if "=" in part:
                toks.append(part)
        updated = False
        for kv in toks:
            k, v = kv.split("=", 1)
            k = k.strip().lower()
            try:
                fv = float(v)
            except Exception:
                continue
            if k.startswith("mono") or k.startswith("l") or k.startswith("r") or k == "energy":
                self.state[k] = _clamp01(fv)
                updated = True

        if updated and "energy" not in self.state:
            e = 0.0
            for i in range(7):
                e += float(self.state.get(f"mono{i}", 0.0))
            self.state["energy"] = _clamp01(e / 7.0)

        if updated:
            self.state = self._apply_gain_smooth(dict(self.state))
            try:
                self.recorder.add_frame(self.state)
            except Exception:
                pass

def list_serial_ports():
    """Return a list of serial port device names (best-effort)."""
    try:
        import serial.tools.list_ports  # type: ignore
        return [p.device for p in serial.tools.list_ports.comports()]
    except Exception:
        return []
