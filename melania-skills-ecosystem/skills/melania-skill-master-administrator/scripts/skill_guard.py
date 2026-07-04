#!/usr/bin/env python3
"""skill_guard.py — захист melania-skill-master-administrator від регресій"""
import json, hashlib, sys
from pathlib import Path
from datetime import datetime, timezone

SKILL_PATH = Path(__file__).parent.parent / "SKILL.md"
SNAP_PATH = Path(__file__).parent / ".snapshots" / "latest.json"

CANONICAL_TERMS = [
    "Master Administrator",
    "Self-Development Engine",
    "Update Workflow",
    "Post-Use Assessment",
    "GAP CHECK",
    "PATTERN CHECK",
    "validation-mesh",
    "CHANGELOG",
    "Core Rules",
    "skill-creator",
    "continuation-memory",
    "compatibility",
    "ai-core-runtime",
    "n8n-orchestrator",
    "semantic-router",
]
MIN_LINES = 100

def get_behavior_rows(text):
    rows = 0
    in_table = False
    for line in text.splitlines():
        if "| Ситуація" in line or "| Умова" in line:
            in_table = True
        elif in_table and line.startswith("|") and "---" not in line:
            rows += 1
        elif in_table and not line.startswith("|"):
            in_table = False
    return rows

def snapshot():
    text = SKILL_PATH.read_text()
    snap = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "md5": hashlib.md5(text.encode()).hexdigest(),
        "total_lines": len(text.splitlines()),
        "terms": {t: (t in text) for t in CANONICAL_TERMS},
        "behavior_rows": get_behavior_rows(text),
    }
    SNAP_PATH.parent.mkdir(exist_ok=True)
    SNAP_PATH.write_text(json.dumps(snap, indent=2, ensure_ascii=False))
    print(f"✅ Snapshot: {snap['total_lines']} рядків · MD5: {snap['md5'][:16]}")

def validate():
    if not SNAP_PATH.exists():
        print("❌ Snapshot відсутній. Запусти: --snapshot"); sys.exit(1)
    snap = json.loads(SNAP_PATH.read_text())
    text = SKILL_PATH.read_text()
    errors = []
    for term, was in snap["terms"].items():
        if was and term not in text:
            errors.append(f"ВІДСУТНІЙ: '{term}'")
    cur = len(text.splitlines())
    if cur < snap["total_lines"] * 0.82:
        errors.append(f"Скорочення: {snap['total_lines']}→{cur} рядків")
    if "Master Administrator" not in text:
        errors.append("MA Protocol видалено!")
    if "Self-Development Engine" not in text:
        errors.append("Self-Dev Engine видалено!")
    if errors:
        print(f"❌ ЗАБЛОКОВАНО — {len(errors)} помилок:")
        for e in errors: print(f"  ✗ {e}")
        sys.exit(1)
    print(f"✅ VALID — {cur} рядків · всі терміни присутні")

if __name__ == "__main__":
    if "--snapshot" in sys.argv: snapshot()
    elif "--validate" in sys.argv: validate()
    else: print("Використання: --snapshot | --validate")
