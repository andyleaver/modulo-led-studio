from __future__ import annotations
import json, os

def run():
    root = os.path.dirname(os.path.dirname(__file__))
    p = os.path.join(root, "fixtures", "audio_presets", "Stereo14_EQ_to_HealthShield.json")
    with open(p, "r", encoding="utf-8") as f:
        data=json.load(f)
    assert "audio_routes" in data and len(data["audio_routes"])>0
