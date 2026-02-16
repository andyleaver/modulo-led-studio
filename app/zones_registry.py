# Project-level Zones/Groups registry (engine-facing, UI-agnostic)
# Stores reusable named targets with stable ids.
import uuid

def _uid():
    return uuid.uuid4().hex[:12]

class ZonesRegistry:
    def __init__(self):
        self._zones = {}   # id -> dict
        self._groups = {}  # id -> dict

    # ---- Zones (ranges) ----
    def add_zone(self, name, indices):
        zid = _uid()
        self._zones[zid] = {"id": zid, "name": name, "indices": list(indices)}
        return zid

    def update_zone(self, zid, indices=None, name=None):
        z = self._zones.get(zid)
        if not z: return False
        if indices is not None: z["indices"] = list(indices)
        if name is not None: z["name"] = name
        return True

    def get_zone(self, zid):
        return self._zones.get(zid)

    def all_zones(self):
        return list(self._zones.values())

    # ---- Groups (explicit indices) ----
    def add_group(self, name, indices):
        gid = _uid()
        self._groups[gid] = {"id": gid, "name": name, "indices": list(indices)}
        return gid

    def update_group(self, gid, indices=None, name=None):
        g = self._groups.get(gid)
        if not g: return False
        if indices is not None: g["indices"] = list(indices)
        if name is not None: g["name"] = name
        return True

    def get_group(self, gid):
        return self._groups.get(gid)

    def all_groups(self):
        return list(self._groups.values())

    # ---- Resolve ----
    def resolve_indices(self, kind, tid):
        if kind == 'zone':
            z = self._zones.get(tid)
            return list(z.get('indices', [])) if z else []
        if kind == 'group':
            g = self._groups.get(tid)
            return list(g.get('indices', [])) if g else []
        return []
