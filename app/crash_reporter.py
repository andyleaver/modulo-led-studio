from __future__ import annotations
import os, sys, time, traceback
from pathlib import Path

# --- diagnostics helper (no silent failure) ---
try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None

def _diag_exc(e: Exception, where: str):
    try:
        if _DIAGS is not None:
            _DIAGS.exception(e, domain="PROJECT", code="CRASH_REPORTER_EXCEPTION", summary=where)
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[1]

def _now_stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())

def write_report(exc_type, exc, tb) -> Path:
    outdir = ROOT / "out" / "crash_reports"
    outdir.mkdir(parents=True, exist_ok=True)
    p = outdir / f"crash_{_now_stamp()}.txt"

    # diagnostics (best effort)
    diag = ""
    try:
        from app.diagnostics import as_text as _diag
        diag = _diag()
    except Exception:
        diag = "(diagnostics unavailable)\n"

    # recent log
    log_tail = ""
    try:
        from app.log_buffer import tail
        log_tail = "".join(tail(250))
    except Exception:
        log_tail = "(log unavailable)\n"

    trace = "".join(traceback.format_exception(exc_type, exc, tb))

    p.write_text(
        "MODULO CRASH REPORT\n"
        f"timestamp={_now_stamp()}\n"
        f"argv={sys.argv}\n"
        "\n--- diagnostics ---\n"
        + diag +
        "\n--- recent log ---\n"
        + log_tail +
        "\n--- traceback ---\n"
        + trace,
        encoding="utf-8",
        errors="ignore",
    )
    return p

def install_global():
    def _hook(exc_type, exc, tb):
        try:
            rp = write_report(exc_type, exc, tb)
            sys.stderr.write(f"\n[Modulo] Crash report written: {rp}\n")
        except Exception as e:
            _diag_exc(e, "app/crash_reporter.py")
        # also print default
        sys.__excepthook__(exc_type, exc, tb)
    sys.excepthook = _hook
