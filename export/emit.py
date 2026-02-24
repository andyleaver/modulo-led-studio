from __future__ import annotations

"""
Unified export emitter entrypoint.

- Resolves backends + hw config using export.targets.registry helpers
- Delegates code generation to the selected target emitter module
- Writes final artifact (.ino or .zip) into out_path.parent
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple
import zipfile


def _ascii_qr(payload: str) -> str:
    """Render a small ASCII QR for copy/paste-friendly export reports.

    Uses the optional 'qrcode' package if present; otherwise returns empty string.
    """
    payload = str(payload or "").strip()
    if not payload:
        return ""
    try:
        import qrcode  # type: ignore
        from qrcode.constants import ERROR_CORRECT_L
        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_L,
            box_size=1,
            border=1,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        m = qr.get_matrix()
        black = "██"
        white = "  "
        lines = ["".join(black if c else white for c in row) for row in m]
        return "\n".join(lines) + "\n"
    except Exception:
        return ""


def _validate_export_artifact_text(text: str) -> list[str]:
    """Fail-loud validation for generated artifacts.

    We are preventing silent export corruption caused by unreplaced template tokens
    or accidental Python formatting artifacts.

    Returns list of problems (empty => OK).
    """
    probs = []
    t = text or ""
    # Unreplaced @@TOKENS@@
    try:
        import re
        toks = sorted(set(re.findall(r"@@[A-Z0-9_]+@@", t)))
        if toks:
            probs.append("Unreplaced template tokens: " + ", ".join(toks[:50]) + (f" …(+{len(toks)-50})" if len(toks) > 50 else ""))
    except Exception:
        pass

    # Accidental Python format/f-string artifacts
    suspicious = ["{engine.", "{len(", "{self.", "{project", "{ir.", "{selection", "{hw", "{aud", "{{", "}}"]
    found = [s for s in suspicious if s in t]
    if found:
        probs.append("Suspicious formatting artifacts found: " + ", ".join(found))

    # Common placeholder strings
    for s in ["REPLACE_ME", "TODO_TOKEN", "TEMPLATE_TOKEN"]:
        if s in t:
            probs.append(f"Placeholder '{s}' still present")

    return probs


def _validate_written_artifact(path: Path) -> None:
    """Validate the emitted file before we consider export successful."""
    try:
        if not path.exists() or not path.is_file():
            return
        if path.suffix.lower() not in (".ino", ".h", ".hpp", ".c", ".cpp", ".txt"):
            return
        txt = path.read_text(encoding="utf-8", errors="replace")
        probs = _validate_export_artifact_text(txt)
        if probs:
            # Delete corrupt output to prevent false success.
            try:
                path.unlink()
            except Exception:
                pass
            raise RuntimeError("Export validation failed:\n- " + "\n- ".join(probs))
    except Exception:
        raise


from export.targets.registry import (
    load_target,
    resolve_requested_backends,
    resolve_requested_hw,
    resolve_requested_audio_hw,
)


@dataclass
class EmitResult:
    written_path: Path
    report_text: str


def emit_project(*, project: Dict[str, Any], out_path: Path, target_id: str, output_mode: str) -> Tuple[Path, str]:
    out_path = Path(out_path)
    output_mode = str(output_mode or "arduino").strip().lower()

    target = load_target(target_id)
    meta = getattr(target, "meta", None) or {}

    # Resolve selection + hardware
    selection = resolve_requested_backends(project or {}, meta)
    hw = resolve_requested_hw(project or {}, meta)
    aud = resolve_requested_audio_hw(project or {}, meta, selection.get("audio_backend"))

    # Validate msg eq7 audio hw required (already also in parity gates in some builds, but keep fail-closed)
    if (selection.get("audio_backend") or "").lower() == "msgeq7":
        missing = []
        for k in ("msgeq7_reset_pin","msgeq7_strobe_pin","msgeq7_left_pin","msgeq7_right_pin"):
            if not str((aud or {}).get(k) or "").strip():
                missing.append(k)
        if missing:
            raise RuntimeError("Missing required MSGEQ7 audio_hw fields after resolve: " + ", ".join(missing))

    # Delegate to target emitter
    if not hasattr(target, "emit") or not callable(getattr(target, "emit")):
        raise RuntimeError(f"Target '{target_id}' missing emit(project, out_path, output_mode, selection, hw, audio_hw)")

    from export.ir import ShowIR
    ir = ShowIR.from_project(project, selection, hw, aud)
    written, rep = target.emit(
        ir=ir,
        out_path=out_path,
        output_mode=output_mode,
        selection=selection,
        hw=hw,
        audio_hw=aud,
    )
    written_p = Path(written)
    rep = str(rep or "")

    # Release R8: fail-loud validation of generated artifacts
    _validate_written_artifact(written_p)

    # If the target emitted a PlatformIO folder and the caller requested a zip, zip it here (single authority).
    if output_mode.startswith("platformio") or output_mode in ("pio_zip",):
        if written_p.exists() and written_p.is_dir():
            zip_path = out_path.parent / (out_path.stem + ".zip")
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for fp in written_p.rglob("*"):
                    if fp.is_file():
                        zf.write(fp, arcname=str(fp.relative_to(written_p)))
            rep = rep + f"\nFinal artifact: {zip_path.name} (zipped PlatformIO project)\n"
            return zip_path, rep

    # WiFi/Web Update helper (ESP32 targets that support it)
    try:
        exp = (project or {}).get("export") or {}
        hub = exp.get("hub75") or {}
        if isinstance(hub, dict):
            we = str(hub.get("wifi_enable") or hub.get("wifi") or "0").strip().lower()
            wifi_on = we in ("1","true","yes","on","enabled")
            ssid = str(hub.get("wifi_ssid") or "").strip()
            host = str(hub.get("wifi_hostname") or "modulo-hub75").strip()
            apfb = str(hub.get('wifi_ap_fallback') or '0').strip().lower() in ('1','true','yes','on','enabled')
            ntp_on = str(hub.get('wifi_ntp') or '1').strip().lower() in ('1','true','yes','on','enabled')
            tz = str(hub.get('wifi_tz') or 'GMT0BST,M3.5.0/1,M10.5.0/2').strip()
            if wifi_on and (ssid or apfb):
                # Keep report copy/paste friendly
                rep += "\n=== WiFi / Web Update ===\n"
                rep += f"WiFi: ENABLED (SSID: {ssid})\n"
                rep += f"Hostname: {host}  (try: http://{host}.local/)\n"
                rep += f"NTP time sync: {{'ENABLED' if ntp_on else 'disabled'}} (TZ: {tz})\n"
                # Optional QR cards (requires optional 'qrcode' package). Handy for phone setup.
                try:
                    url_host = f"http://{host}.local/"
                    url_ap = "http://192.168.4.1/wifi"
                    rep += "\\nQR (open updater): " + url_host + "\\n"
                    q1 = _ascii_qr(url_host)
                    if q1:
                        rep += q1 + "\\n"
                    if apfb:
                        rep += "QR (WiFi setup portal): " + url_ap + "\\n"
                        q2 = _ascii_qr(url_ap)
                        if q2:
                            rep += q2 + "\\n"
                except Exception:
                    pass
                rep += "Update page: http://<device-ip>/\n"
                rep += "Upload endpoint: http://<device-ip>/update\n\n"
                if apfb:
                    rep += "\nSetup AP fallback: ENABLED\n"
                    rep += "If the device can't join WiFi, it will start an AP named <hostname>-setup.\n"
                    rep += "Connect and open: http://192.168.4.1/wifi\n"

                rep += "Status JSON: http://<device-ip>/info\n\n"
                rep += "First-time setup:\n"
                rep += "  1) Flash once over USB (to get WiFi onto the device).\n"
                rep += "  2) Open Serial Monitor to see the IP address, or check your router DHCP list.\n"
                rep += "  3) Browse to the IP (or hostname.local) and upload the new .bin.\n\n"
                rep += "How to get a .bin:\n"
                rep += "  - Arduino IDE: Sketch → Export compiled Binary\n"
                rep += "  - PlatformIO: build and use the produced firmware.bin\n"
    except Exception:
        pass

    return written_p, rep