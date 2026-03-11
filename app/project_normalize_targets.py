from typing import Any, Dict, List, Tuple

from app.project_apply import replace_project_root
from .project_normalize_support import as_int_list, clamp_indices, layout_count


def normalize_targets(project: Dict[str, Any], changes: List[str]) -> Dict[str, Any]:
    p = dict(project)
    count = layout_count(p)

    zones = p.get("zones") or {}
    if not isinstance(zones, dict):
        zones = {}
        changes.append("zones reset (was not dict)")

    groups = p.get("groups") or {}
    if not isinstance(groups, dict):
        groups = {}
        changes.append("groups reset (was not dict)")

    zones2: Dict[str, Any] = {}
    for name, node in zones.items():
        if not isinstance(name, str) or not name.strip():
            changes.append("dropped zone with invalid name")
            continue
        node = node if isinstance(node, dict) else {}
        idx = clamp_indices(as_int_list(node.get("indices")), count)
        node2 = dict(node)
        node2["indices"] = idx
        zones2[name] = node2
        if node.get("indices") != idx:
            changes.append(f"zone '{name}' indices normalized")
    p = replace_project_root(p, "zones", zones2)

    groups2: Dict[str, Any] = {}
    for name, node in groups.items():
        if not isinstance(name, str) or not name.strip():
            changes.append("dropped group with invalid name")
            continue
        node = node if isinstance(node, dict) else {}
        idx = clamp_indices(as_int_list(node.get("indices")), count)
        node2 = dict(node)
        node2["indices"] = idx
        groups2[name] = node2
        if node.get("indices") != idx:
            changes.append(f"group '{name}' indices normalized")
    p = replace_project_root(p, "groups", groups2)

    masks = p.get("masks") or {}
    if not isinstance(masks, dict):
        masks = {}
        changes.append("masks reset (was not dict)")

    layers = p.get("layers")
    if isinstance(layers, list):
        zone_names = list(zones2.keys())
        group_names = list(groups2.keys())
        new_layers = []
        changed_any = False
        for layer in layers:
            if not isinstance(layer, dict):
                new_layers.append(layer)
                continue
            target_kind = str(layer.get("target_kind", "all") or "all").lower().strip()
            target_ref = layer.get("target_ref", 0)
            try:
                target_ref_int = int(target_ref)
            except Exception:
                target_ref_int = 0
            valid = True
            if target_kind == "zone":
                valid = 0 <= target_ref_int < len(zone_names)
            elif target_kind == "group":
                valid = 0 <= target_ref_int < len(group_names)
            elif target_kind == "all":
                valid = True
            else:
                valid = False
            if not valid:
                layer2 = dict(layer)
                layer2["target_kind"] = "all"
                layer2["target_ref"] = 0
                new_layers.append(layer2)
                changed_any = True
            else:
                if target_ref_int != target_ref:
                    layer2 = dict(layer)
                    layer2["target_ref"] = target_ref_int
                    new_layers.append(layer2)
                    changed_any = True
                else:
                    new_layers.append(layer)
        if changed_any:
            p = replace_project_root(p, "layers", new_layers)
            changes.append("normalized layer target_kind/target_ref refs")

    masks2 = dict(masks)
    for zone_name, zone_node in zones2.items():
        key = f"zone:{zone_name}"
        want = {"type": "indices", "indices": list(zone_node.get("indices") or [])}
        if masks2.get(key) != want:
            masks2[key] = want
            changes.append(f"synced mask '{key}' from zones")
    for group_name, group_node in groups2.items():
        key = f"group:{group_name}"
        want = {"type": "indices", "indices": list(group_node.get("indices") or [])}
        if masks2.get(key) != want:
            masks2[key] = want
            changes.append(f"synced mask '{key}' from groups")
    p = replace_project_root(p, "masks", masks2)

    ui = p.get("ui")
    if not isinstance(ui, dict):
        ui = {}
        p = replace_project_root(p, "ui", ui)

    top_level_target_mask = p.get("target_mask") if "target_mask" in p else None
    if top_level_target_mask is not None and ui.get("target_mask") is None and isinstance(top_level_target_mask, str):
        ui2 = dict(ui)
        ui2["target_mask"] = top_level_target_mask
        p = replace_project_root(p, "ui", ui2)
        ui = p.get("ui") or ui2
        changes.append("migrated top-level target_mask -> ui.target_mask")
    if "target_mask" in p:
        del p["target_mask"]
        changes.append("removed deprecated top-level target_mask")

    target_mask = ui.get("target_mask")
    if target_mask is not None and (not isinstance(target_mask, str) or target_mask not in masks2):
        ui2 = dict(ui)
        ui2["target_mask"] = None
        p = replace_project_root(p, "ui", ui2)
        changes.append("cleared invalid ui.target_mask")

    return p
