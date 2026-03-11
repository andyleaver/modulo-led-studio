from typing import Any, Dict, List, Tuple

from .project_normalize_support import diag_exc
from .project_normalize_targets import normalize_targets
from .project_normalize_state import normalize_state


def normalize_project_zones_masks_groups(project: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Return (new_project, changes) with deterministic Zones/Groups/Masks and canonical UI/audio state."""
    if not isinstance(project, dict):
        return {}, ["project was not a dict; reset to {}"]

    changes: List[str] = []
    try:
        normalized = normalize_targets(project, changes)
        normalized = normalize_state(normalized, changes)
        return normalized, changes
    except Exception as error:
        diag_exc(error, 'app/project_normalize.py')
        return dict(project), changes
