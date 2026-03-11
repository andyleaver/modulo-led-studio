#!/usr/bin/env python3
"""
Export Inventory Audit

Purpose:
- Enumerate every target pack and its *verifiable* surface/mapping capabilities from target.json.
- Produce a markdown report for docs/EXPORT_INVENTORY.md and a machine-readable JSON at docs/EXPORT_INVENTORY.json.

This is NOT a roadmap. It's an audit of what's implemented and declared by target packs.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))

TARGETS_DIR = os.path.join(REPO_ROOT, "export", "targets")

OUT_MD = os.path.join(REPO_ROOT, "docs", "EXPORT_INVENTORY.md")
OUT_JSON = os.path.join(REPO_ROOT, "docs", "EXPORT_INVENTORY.json")

def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _safe_get(d: Dict[str, Any], key: str, default=None):
    v = d.get(key, default)
    return default if v is None else v

def _format_bool(v: Any) -> str:
    if v is True:
        return "YES"
    if v is False:
        return "NO"
    return "?"

def _pick_surface(meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Target packs historically vary in how they describe surfaces.
    This helper extracts commonly-used surface descriptors for auditing.
    """
    surf: Dict[str, Any] = {}
    # Common keys we've used across packs
    for k in ("strip", "matrix", "hub75", "mapping", "surface", "surfaces", "layout"):
        if k in meta:
            surf[k] = meta.get(k)
    return surf

def _summ_surface(meta: Dict[str, Any]) -> Tuple[str, str]:
    """
    Return (surface_summary, mapping_summary)
    """
    strip = meta.get("strip") or {}
    matrix = meta.get("matrix") or {}
    mapping = meta.get("mapping") or {}

    # Strip
    strip_count = strip.get("count") or strip.get("leds") or strip.get("count")
    strip_summary = "—" if not strip_count else f"strip:{strip_count}"

    # Matrix
    mw = matrix.get("width") or matrix.get("w")
    mh = matrix.get("height") or matrix.get("h")
    matrix_summary = "—"
    if mw and mh:
        matrix_summary = f"matrix:{mw}x{mh}"
    elif mw or mh:
        matrix_summary = f"matrix:{mw or '?'}x{mh or '?'}"

    # Combine
    surface_summary = strip_summary
    if matrix_summary != "—":
        surface_summary = f"{strip_summary}, {matrix_summary}" if strip_summary != "—" else matrix_summary

    # Mapping
    serp = mapping.get("serpentine")
    origin = mapping.get("origin")
    order = mapping.get("order") or mapping.get("pixel_order") or mapping.get("color_order")
    mapping_parts: List[str] = []
    if serp is not None:
        mapping_parts.append(f"serp={_format_bool(serp)}")
    if origin:
        mapping_parts.append(f"origin={origin}")
    if order:
        mapping_parts.append(f"order={order}")
    mapping_summary = ", ".join(mapping_parts) if mapping_parts else "—"

    return surface_summary, mapping_summary

def audit() -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []

    for name in sorted(os.listdir(TARGETS_DIR)):
        tdir = os.path.join(TARGETS_DIR, name)
        if not os.path.isdir(tdir):
            continue
        meta_path = os.path.join(tdir, "target.json")
        if not os.path.exists(meta_path):
            continue

        meta = _load_json(meta_path)
        caps = meta.get("capabilities") or {}

        surface_summary, mapping_summary = _summ_surface(meta)

        rows.append({
            "id": _safe_get(meta, "id", name),
            "name": _safe_get(meta, "name", name),
            "vendor": _safe_get(meta, "vendor", ""),
            "family": _safe_get(meta, "family", ""),
            "surface_summary": surface_summary,
            "mapping_summary": mapping_summary,
            "capabilities": caps,
            "surface_raw": _pick_surface(meta),
            "path": os.path.relpath(meta_path, REPO_ROOT).replace("\\", "/"),
        })

    return {
        "generated_by": "tools/export_inventory_audit.py",
        "targets_dir": os.path.relpath(TARGETS_DIR, REPO_ROOT).replace("\\", "/"),
        "targets_total": len(rows),
        "targets": rows,
    }

def write_outputs(payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)

    # JSON
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=False)

    # Markdown
    lines: List[str] = []
    lines.append("# Export inventory (audited from target packs)")
    lines.append("")
    lines.append("This is a *code-derived* inventory of target packs (exporters/boards) and the **declared** surface + mapping fields in each `export/targets/*/target.json`.")
    lines.append("")
    lines.append("It is intended to answer one question: **what can we verifiably preview + export today?**")
    lines.append("")
    lines.append(f"- Targets total: **{payload['targets_total']}**")
    lines.append(f"- Generated file: `docs/EXPORT_INVENTORY.json`")
    lines.append("")

    # Table
    lines.append("| id | name | vendor | family | surface | mapping |")
    lines.append("|---|---|---|---|---|---|")
    for t in payload["targets"]:
        lines.append(
            f"| `{t['id']}` | {t['name']} | {t['vendor']} | {t['family']} | {t['surface_summary']} | {t['mapping_summary']} |"
        )
    lines.append("")
    lines.append("## Per-target details")
    lines.append("")
    for t in payload["targets"]:
        lines.append(f"### `{t['id']}` — {t['name']}")
        lines.append(f"- Source: `{t['path']}`")
        if t.get("vendor"):
            lines.append(f"- Vendor: {t['vendor']}")
        if t.get("family"):
            lines.append(f"- Family: {t['family']}")
        lines.append(f"- Surface: {t['surface_summary']}")
        lines.append(f"- Mapping: {t['mapping_summary']}")
        lines.append("")
        lines.append("Declared capabilities:")
        caps = t.get("capabilities") or {}
        if not caps:
            lines.append("- (none declared)")
        else:
            # small, stable ordering
            for k in sorted(caps.keys()):
                lines.append(f"- `{k}`: `{caps[k]}`")
        lines.append("")
        lines.append("Raw surface fields:")
        sr = t.get("surface_raw") or {}
        if not sr:
            lines.append("- (none)")
        else:
            lines.append("```json")
            lines.append(json.dumps(sr, indent=2, sort_keys=True))
            lines.append("```")
        lines.append("")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

def main() -> int:
    payload = audit()
    write_outputs(payload)
    print(f"[export_inventory_audit] wrote: {os.path.relpath(OUT_MD, REPO_ROOT)}")
    print(f"[export_inventory_audit] wrote: {os.path.relpath(OUT_JSON, REPO_ROOT)}")
    print(f"[export_inventory_audit] targets: {payload['targets_total']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
