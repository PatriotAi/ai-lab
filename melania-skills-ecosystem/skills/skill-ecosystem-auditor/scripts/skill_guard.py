#!/usr/bin/env python3
"""skill_guard.py — захист skill-ecosystem-auditor від регресій.
Використання: --snapshot | --validate"""
import json, hashlib, sys
from pathlib import Path
from datetime import datetime, timezone

SKILL_PATH = Path(__file__).parent.parent / "SKILL.md"
SNAP_PATH = Path(__file__).parent / ".snapshots" / "latest.json"

CANONICAL_TERMS = [
    "Decision Gate",
    "Anti-repeat Engine",
    "read-only",
    "validation-mesh",
    "continuation-memory",
    "semantic-router",
    "skill-creation-guide",
    "melania-skill-master-administrator",
    "Self-Dev Proposal",
    "українською-перш",
    "deprecation",
    "Master Administrator",
    "diff",
]
MIN_LINES = 90

def behavior_rows(text):
    rows, intbl = 0, False
    for line in text.splitlines():
        if "| Ситуація" in line or "| Умова" in line:
            intbl = True
        elif intbl and line.startswith("|") and "---" not in line:
            rows += 1
        elif intbl and not line.startswith("|"):
            intbl = False
    return rows

def snapshot():
    text = SKILL_PATH.read_text(encoding="utf-8")
    snap = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "md5": hashlib.md5(text.encode()).hexdigest(),
        "total_lines": len(text.splitlines()),
        "terms": {t: (t in text) for t in CANONICAL_TERMS},
        "behavior_rows": behavior_rows(text),
    }
    SNAP_PATH.parent.mkdir(exist_ok=True)
    SNAP_PATH.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Snapshot: {snap['total_lines']} рядків · MD5: {snap['md5'][:16]} · gate-рядків: {snap['behavior_rows']}")

def validate():
    if not SNAP_PATH.exists():
        print("❌ Snapshot відсутній. Запусти: --snapshot"); sys.exit(1)
    snap = json.loads(SNAP_PATH.read_text(encoding="utf-8"))
    text = SKILL_PATH.read_text(encoding="utf-8")
    errors = []
    for term, was in snap["terms"].items():
        if was and term not in text:
            errors.append(f"ВІДСУТНІЙ термін: '{term}'")
    cur = len(text.splitlines())
    if cur < snap["total_lines"] * 0.82:
        errors.append(f"Скорочення: {snap['total_lines']}→{cur} рядків (>18%)")
    if cur < MIN_LINES:
        errors.append(f"Замало рядків: {cur} < {MIN_LINES}")
    if "Decision Gate" not in text:
        errors.append("Decision Gate видалено!")
    if "read-only" not in text:
        errors.append("Гарантію read-only видалено!")
    if errors:
        print(f"❌ ЗАБЛОКОВАНО — {len(errors)} помилок:")
        for e in errors: print(f"  ✗ {e}")
        sys.exit(1)
    print(f"✅ VALID — {cur} рядків · усі терміни присутні · gate-рядків: {behavior_rows(text)}")

if __name__ == "__main__":
    if "--snapshot" in sys.argv: snapshot()
    elif "--validate" in sys.argv: validate()
    else: print("Використання: --snapshot | --validate")
