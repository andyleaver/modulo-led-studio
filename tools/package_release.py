#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import shutil
import stat
from datetime import datetime, UTC
from pathlib import Path
import zipfile

sys.dont_write_bytecode = True
os.environ.setdefault('PYTHONDONTWRITEBYTECODE', '1')

REPO_ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {
    '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
    '.venv', 'venv', 'dist', 'parity_reports', 'artifacts', 'out', '.git'
}
EXCLUDE_FILE_SUFFIXES = {'.pyc', '.pyo'}
EXCLUDE_PREFIXES = ('tmp_',)


def _read_app_id() -> str:
    app_id_path = REPO_ROOT / 'APP_ID.txt'
    if app_id_path.exists():
        app_id = app_id_path.read_text(encoding='utf-8').strip()
        if app_id:
            return app_id
    return REPO_ROOT.name


def _validate_package_identity(app_id: str) -> None:
    repo_name = REPO_ROOT.name
    if app_id != repo_name:
        raise RuntimeError(
            f'APP_ID.txt ({app_id}) must match the top-level folder name ({repo_name}) for release packaging'
        )


def _artifact_root() -> Path:
    env = os.environ.get('MODULO_ARTIFACT_DIR')
    return Path(env) if env else (REPO_ROOT.parent / 'artifacts')


def _should_skip(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT)
    for part in rel.parts:
        if part in EXCLUDE_DIRS:
            return True
    if path.is_file():
        if path.suffix in EXCLUDE_FILE_SUFFIXES:
            return True
        if any(path.name.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
            return True
    return False


def _ensure_run_sh_exec(staging_root: Path) -> None:
    run_sh = staging_root / 'RUN.sh'
    if run_sh.exists():
        mode = run_sh.stat().st_mode
        run_sh.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def build_package(out_dir: Path | None = None) -> Path:
    app_id = _read_app_id()
    _validate_package_identity(app_id)
    ts = datetime.now(UTC).strftime('%Y%m%d_%H%M%SZ')
    artifact_root = out_dir if out_dir is not None else _artifact_root()
    artifact_root.mkdir(parents=True, exist_ok=True)

    staging_parent = artifact_root / '_package_staging'
    if staging_parent.exists():
        shutil.rmtree(staging_parent)
    staging_root = staging_parent / app_id
    staging_root.mkdir(parents=True, exist_ok=True)

    try:
        for src in REPO_ROOT.rglob('*'):
            if src == REPO_ROOT:
                continue
            if _should_skip(src):
                continue
            rel = src.relative_to(REPO_ROOT)
            dest = staging_root / rel
            if src.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            elif src.is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
        _ensure_run_sh_exec(staging_root)

        zip_path = artifact_root / f'Modulo_Release_{ts}.zip'
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for item in staging_parent.rglob('*'):
                if item.is_file():
                    zf.write(item, item.relative_to(staging_parent))
        return zip_path
    finally:
        if staging_parent.exists():
            shutil.rmtree(staging_parent)


def main() -> int:
    ap = argparse.ArgumentParser(description='Create a clean Modulo release package zip')
    ap.add_argument('--out-dir', default=None, help='Output directory (default: ../artifacts or $MODULO_ARTIFACT_DIR)')
    args = ap.parse_args()
    out_dir = Path(args.out_dir) if args.out_dir else None
    zip_path = build_package(out_dir=out_dir)
    print(zip_path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
