from __future__ import annotations

HELP = {
    "effects": {
        "title": "Effects tab — how to use it",
        "body": (
            "This is where effects live and where you control the SAFE workflow.\n\n"
            "Key columns:\n"
            "• ready: YES/NO based on contracts (fixture, USES, no placeholders, etc.)\n"
            "• next: what you should do next for the selected effect\n\n"
            "Important buttons:\n"
            "• Scaffold…  Creates a new effect skeleton + default fixture.\n"
            "• Make Ready  Ensures SHIPPED flag + USES list + fixture exist.\n"
            "• Smoke Selected  Runs export+preview checks for ONE fixture (fast).\n"
            "• Smoke+Update  Same, but updates golden hashes for that effect.\n"
            "• Promote…  Ships the effect (blocked if TODOs/placeholders exist).\n\n"
            "Output locations:\n• out/ = projects, exports (.ino), autosave, crash reports\n• dist/ = packaged release zips\n\nRule: If preflight fails, do NOT ship. Fix the contract first."
        ),
    },
    "workbench": {
        "title": "Workbench tab — parity implementation cockpit",
        "body": (
            "Workbench is for fast iteration on ONE effect.\n\n"
            "Typical loop:\n"
            "1) Select an effect in Effects tab\n"
            "2) Load from Selected (copies key here)\n"
            "3) Open Effect File + Open Fixture\n"
            "4) Edit parity (preview + Arduino emit)\n"
            "5) Smoke Selected\n"
            "6) Smoke+Update when you want to lock new goldens\n\n"
            "If you are unsure what to do next, go back to Effects tab and read the 'next' column."
        ),
    },
    "start": {
        "title": "Start Here — glossary",
        "body": (
            "Quick glossary:\n\n"
            "• Effect: a behavior module (preview + Arduino export).\n"
            "• Fixture: a small project JSON used for smoke tests and goldens.\n"
            "• Golden hashes: pinned outputs that catch regressions automatically.\n"
            "• Smoke test: runs export+preview for a fixture and compares to goldens.\n"
            "• Preflight: the strict gate (lint + contracts + goldens + shipped parity).\n"
            "• Promote: marks effect SHIPPED=True and adds it to auto_load (shipping list).\n"
            "• Package Beta: creates a clean release zip only if preflight passes.\n\n"
            "Philosophy: you don't 'hope' it works — you prove it with tests."
        ),
    },
}
