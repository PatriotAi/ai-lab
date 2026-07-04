#!/usr/bin/env python3
"""skill_guard.py — універсальний захист скіла від регресій (автокалібрований).
Знімає baseline власного SKILL.md (рядки, заголовки H2/H3, ключові терміни) і
блокує зміни, що видаляють істотну частину чи ключові секції.
Використання: --snapshot | --validate"""
import json, hashlib, re, sys
from pathlib import Path
from datetime import datetime, timezone

SKILL_PATH = Path(__file__).parent.parent / "SKILL.md"
SNAP_PATH = Path(__file__).parent / ".snapshots" / "latest.json"

def headings(text):
    return [l.strip() for l in text.splitlines() if re.match(r'^#{2,3}\s', l)]

def key_terms(text):
    # CamelCase/двослівні терміни в заголовках + слова великими у тілі
    terms=set()
    for h in headings(text):
        h2=re.sub(r'^#{2,3}\s*','',h)
        # перше змістовне слово/фраза до тире
        first=re.split(r'[—\-:(]', h2)[0].strip()
        if 3<=len(first)<=40: terms.add(first)
    return sorted(terms)

def snapshot():
    text=SKILL_PATH.read_text(encoding="utf-8")
    snap={
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "md5": hashlib.md5(text.encode()).hexdigest(),
        "total_lines": len(text.splitlines()),
        "headings": headings(text),
        "key_terms": key_terms(text),
    }
    SNAP_PATH.parent.mkdir(exist_ok=True)
    SNAP_PATH.write_text(json.dumps(snap,indent=2,ensure_ascii=False),encoding="utf-8")
    print(f"✅ Snapshot: {snap['total_lines']} рядків · {len(snap['headings'])} секцій · MD5 {snap['md5'][:12]}")

def validate():
    if not SNAP_PATH.exists():
        print("❌ Snapshot відсутній. Запусти: --snapshot"); sys.exit(1)
    snap=json.loads(SNAP_PATH.read_text(encoding="utf-8"))
    text=SKILL_PATH.read_text(encoding="utf-8")
    errors=[]
    cur=len(text.splitlines())
    if cur < snap["total_lines"]*0.80:
        errors.append(f"Скорочення >20%: {snap['total_lines']}→{cur} рядків")
    cur_h=set(headings(text))
    missing=[h for h in snap["headings"] if h not in cur_h]
    if len(missing) > max(1, len(snap["headings"])//4):
        errors.append(f"Видалено {len(missing)} секцій: {missing[:3]}…")
    # UA-директива має лишатись (українською-перша)
    if "українською за" not in text.lower() and "українською-перш" not in text.lower():
        errors.append("UA-директива (українською-перша) зникла")
    if errors:
        print(f"❌ ЗАБЛОКОВАНО — {len(errors)}:")
        for e in errors: print(f"  ✗ {e}")
        sys.exit(1)
    print(f"✅ VALID — {cur} рядків · {len(cur_h)} секцій · UA-директива на місці")

if __name__=="__main__":
    if "--snapshot" in sys.argv: snapshot()
    elif "--validate" in sys.argv: validate()
    else: print("Використання: --snapshot | --validate")
