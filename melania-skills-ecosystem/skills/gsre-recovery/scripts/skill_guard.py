#!/usr/bin/env python3
"""Універсальний skill guard: --snapshot записує baseline, --validate перевіряє відсутність усадки."""
import sys, json, hashlib, re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SKILL = HERE / "SKILL.md"
SNAP = HERE / ".snapshots" / "baseline.json"

def stats():
    t = SKILL.read_text(encoding="utf-8")
    lines = t.count("\n") + 1
    sections = len(re.findall(r'^## ', t, re.M))
    md5 = hashlib.md5(t.encode("utf-8")).hexdigest()[:12]
    ua = bool(re.search(r'українськ|UA-перш|українською', t, re.I))
    return lines, sections, md5, ua

def snapshot():
    l, s, m, ua = stats()
    SNAP.parent.mkdir(parents=True, exist_ok=True)
    SNAP.write_text(json.dumps({"lines": l, "sections": s, "md5": m, "ua": ua}), encoding="utf-8")
    print(f"✅ Snapshot: {l} рядків · {s} секцій · UA={'✓' if ua else '✗'} · MD5 {m}")

def validate():
    l, s, m, ua = stats()
    if not SNAP.exists():
        print("❌ Snapshot відсутній. Запусти: --snapshot"); sys.exit(1)
    b = json.loads(SNAP.read_text(encoding="utf-8"))
    probs = []
    if l < b["lines"] * 0.9: probs.append(f"рядків {l} < {b['lines']} (усадка >10%)")
    if s < b["sections"]: probs.append(f"секцій {s} < {b['sections']} (видалено)")
    if b.get("ua") and not ua: probs.append("UA-директива зникла")
    if probs:
        print("❌ ЗАБЛОКОВАНО:")
        for p in probs: print(f"  ✗ {p}")
        sys.exit(1)
    print(f"✅ VALID — {l} рядків · {s} секцій · UA={'✓' if ua else '✗'}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "--snapshot": snapshot()
    elif cmd == "--validate": validate()
    else: print("usage: skill_guard.py --snapshot | --validate")
