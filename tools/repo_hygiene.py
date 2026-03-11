from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BANNED_TOP_LEVEL = [
    ROOT / "licenses",
    ROOT / "out",
    ROOT / "dist",
    ROOT / "parity_reports",
]

BANNED_RECURSIVE_DIR_NAMES = {"__pycache__", ".pytest_cache"}
BANNED_RECURSIVE_SUFFIXES = {".pyc", ".pyo"}
BANNED_RECURSIVE_TEXT_SNIPPETS = ["MODULO_LED_STUDIO_PROPER_REFACTOR_STEP", "step247_work", "/mnt/data/step", "RELEASE_NOTES_STEP", "app/beta_freeze.py"]
BANNED_TOP_LEVEL_FILES = {
    "FINAL_UI_POLISH_NOTES.txt",
    "UI_WORKFLOW_STATUS.txt",
    "UI_WORKFLOW.txt",
    "WORKFLOW_OVERVIEW.txt",
    "LAYER_BEHAVIOR_RELATIONSHIP.txt",
    "LAYER_STACK_EXPLAINED.txt",
    "OPERATOR_STACK_EXPLAINED.txt",
    "RULES_AUTOMATION_EXPLAINED.txt",
    "TARGETING_EXPLAINED.txt",
    "UI_WORKFLOW_ORDER.txt",
    "OPERATORS_WORKFLOW.txt",
    "TARGETING_WORKFLOW.txt",
    "RUN_RELEASE_GATE.sh",
    "RULE_EXAMPLES.txt",
    "WORKFLOW_SEQUENCE.txt",
}


def _iter_recursive_junk(root: Path):
    for path in root.rglob("*"):
        parts = set(path.parts)
        if ".git" in parts or "artifacts" in parts or "third_party" in parts:
            continue
        if path.is_dir() and path.name in BANNED_RECURSIVE_DIR_NAMES:
            yield path
        elif path.is_file() and path.suffix in BANNED_RECURSIVE_SUFFIXES:
            yield path


def _iter_text_leaks(root: Path):
    for path in root.rglob("*"):
        parts = set(path.parts)
        if ".git" in parts or "artifacts" in parts or "third_party" in parts or "selftest" in parts:
            continue
        if path == ROOT / "tools" / "repo_hygiene.py":
            continue
        if not path.is_file() or path.suffix.lower() not in {".py", ".md", ".txt", ".json", ".yaml", ".yml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for needle in BANNED_RECURSIVE_TEXT_SNIPPETS:
            if needle in text:
                yield path, needle


def main() -> int:
    problems: list[str] = []

    for path in BANNED_TOP_LEVEL:
        if path.exists():
            problems.append(f"unwanted repo artifact present: {path.relative_to(ROOT)}")

    for path in ROOT.glob("tmp_*"):
        if path.exists():
            problems.append(f"unwanted repo artifact present: {path.relative_to(ROOT)}")

    for path in ROOT.glob("RELEASE_NOTES_STEP*.txt"):
        if path.exists():
            problems.append(f"unwanted repo artifact present: {path.relative_to(ROOT)}")

    retired_guard = ROOT / "app" / "beta_freeze.py"
    if retired_guard.exists():
        problems.append(f"unwanted repo artifact present: {retired_guard.relative_to(ROOT)}")

    for name in sorted(BANNED_TOP_LEVEL_FILES):
        path = ROOT / name
        if path.exists():
            problems.append(f"unwanted repo artifact present: {path.relative_to(ROOT)}")

    for path in _iter_recursive_junk(ROOT):
        problems.append(f"unwanted repo junk present: {path.relative_to(ROOT)}")

    for path, needle in _iter_text_leaks(ROOT):
        problems.append(f"unwanted build-history text present: {path.relative_to(ROOT)} -> {needle}")

    if problems:
        print("REPO HYGIENE FAILED")
        for item in sorted(set(problems)):
            print(f"- {item}")
        return 1

    print("REPO HYGIENE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
