class RulesTabStateMixin:
    def _project(self) -> dict:
        try:
            p = getattr(self.app_core, "project", {}) or {}
            return p if isinstance(p, dict) else {}
        except Exception:
            return {}

    def _set_project(self, p):
        try:
            self.app_core.project = p
        except Exception:
            pass

    def _canonical_addresses(self):
        p = self._project()
        out = []
        layers = p.get("layers") or []
        if isinstance(layers, list):
            for i, ly in enumerate(layers):
                out.extend([
                    f"layers[{i}].enabled",
                    f"layers[{i}].name",
                    f"layers[{i}].opacity",
                    f"layers[{i}].blend_mode",
                    f"layers[{i}].target_kind",
                    f"layers[{i}].target_ref",
                    f"layers[{i}].behavior",
                ])
                if isinstance(ly, dict):
                    params = ly.get("params") or {}
                    if isinstance(params, dict):
                        for k in sorted(params.keys()):
                            out.append(f"layers[{i}].params.{k}")
        postfx = p.get("postfx") or {}
        if isinstance(postfx, dict):
            for k in sorted(postfx.keys()):
                out.append(f"project.postfx.{k}")
        rules = p.get("rules") or []
        if isinstance(rules, list) and rules:
            out.append("rules[*]")
        vars_dict = p.get("vars") or p.get("variables") or {}
        if isinstance(vars_dict, dict):
            for k in sorted(vars_dict.keys()):
                out.append(f"vars.{k}")
        seen = set()
        uniq = []
        for a in out:
            if a not in seen:
                uniq.append(a)
                seen.add(a)
        return uniq

    def _address_summary_text(self):
        addrs = self._canonical_addresses()
        layer_base = 0
        layer_params = 0
        postfx = 0
        vars_count = 0
        other = 0
        for a in addrs:
            if a.startswith("layers[") and ".params." in a:
                layer_params += 1
            elif a.startswith("layers["):
                layer_base += 1
            elif a.startswith("project.postfx."):
                postfx += 1
            elif a.startswith("vars.") or a.startswith("variables."):
                vars_count += 1
            else:
                other += 1
        return (
            f"Address Summary: layer fields {layer_base} · "
            f"layer params/bindings {layer_params} · "
            f"operator keys {postfx} · vars {vars_count}"
            + (f" · other {other}" if other else "")
        )

    def _rules_gates(self):
        try:
            fn = getattr(self.app_core, "get_era_gates", None)
            return dict(fn() if callable(fn) else {})
        except Exception:
            return {}
