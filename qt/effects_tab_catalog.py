from __future__ import annotations

from typing import Any, Dict, List, Optional


class EffectsTabCatalogMixin:
    def _catalog(self) -> Dict[str, Any]:
        try:
            from behaviors.registry import load_capabilities_catalog
            return load_capabilities_catalog() or {}
        except Exception:
            return {}

    def _all_rows(self) -> List[Dict[str, Any]]:
        try:
            from behaviors.registry import list_effect_keys
            keys = list_effect_keys() or []
        except Exception:
            keys = []
        cat_root = self._catalog()
        cat = cat_root.get("effects", {}) if isinstance(cat_root, dict) else {}
        out: List[Dict[str, Any]] = []
        for k in sorted(set(keys)):
            meta = cat.get(k) if isinstance(cat, dict) else None
            if not isinstance(meta, dict):
                meta = {}
            out.append({
                "key": k,
                "title": str(meta.get("title") or k),
                "desc": str(meta.get("desc") or meta.get("description") or ""),
                "shipped": bool(meta.get("shipped", True)),
                "hidden": bool(meta.get("hidden", False)),
            })
        return out

    def _era_gates(self) -> Dict[str, Any]:
        try:
            fn = getattr(self.app_core, "get_era_gates", None)
            gates = fn() if callable(fn) else {}
            return dict(gates or {})
        except Exception:
            return {}

    def _allowed_effects_for_era(self) -> Optional[List[str]]:
        gates = self._era_gates()
        raw = gates.get("allowed_effects", None)
        if raw is None:
            return None
        try:
            return [str(x) for x in list(raw)]
        except Exception:
            return None

    def _era_max_layers(self) -> int:
        gates = self._era_gates()
        try:
            return int(gates.get("max_layers", 99) or 99)
        except Exception:
            return 99

    def _update_era_gate_status(self, total_count: int, shown_count: int):
        gates = self._era_gates()
        allowed = self._allowed_effects_for_era()
        model = str(gates.get("control_model") or "").strip().lower()
        max_layers = self._era_max_layers()

        if allowed is None:
            msg = (
                f"Era gate: no explicit behavior filter in this control model ({model or 'full_modulo'}). "
                f"Layer limit: {max_layers}."
            )
        else:
            msg = (
                f"Era gate: showing {shown_count} historically allowed behavior(s) out of {total_count}. "
                f"Layer limit: {max_layers}."
            )
        try:
            self.lbl_era_gate_status.setText(msg)
        except Exception:
            pass
