from __future__ import annotations

import json

from app.project_canonical import canonicalize_project_dict
from app.project_defaults import DEFAULT_PROJECT


def migrate_project_dict(p: dict) -> dict:
  """Best-effort migration for loaded project dicts.

  Deterministic: migrates known legacy schema into canonical fields and removes
  redundant legacy keys. Import-compat lives here; runtime stays canonical-only.
  """
  if not isinstance(p, dict):
    return json.loads(json.dumps(DEFAULT_PROJECT))
  p2, _changes = canonicalize_project_dict(p)
  return p2


__all__ = [
  'migrate_project_dict',
]
