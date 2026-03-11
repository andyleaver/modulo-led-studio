from __future__ import annotations
import json, os

def run():
    root = os.path.dirname(os.path.dirname(__file__))
    p = os.path.join(root, "fixtures", "audio_presets", "Stereo14_EQ_to_HealthShield.json")
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data.get("audio"), dict)
    routes = data["audio"].get("routes")
    assert isinstance(routes, list) and len(routes) > 0
    assert "audio_routes" not in data
