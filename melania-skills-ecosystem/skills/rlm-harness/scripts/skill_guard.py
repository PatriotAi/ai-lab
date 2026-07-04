#!/usr/bin/env python3
"""
skill_guard.py — regression guard for rlm-harness.
Перевіряє, що ключові інваріанти (canonical terms) присутні в SKILL.md.
Використання:
    python3 skill_guard.py --validate     # exit 1 якщо щось зникло
    python3 skill_guard.py --snapshot      # зберегти snapshot перед записом
Без залежностей. Узгоджено з конвенцією melania (guard перед пакуванням).
"""
import sys, os, json, hashlib, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "..", "SKILL.md")
SNAP_DIR = os.path.join(HERE, "..", ".snapshots")

# Canonical terms — кожен мусить лишатися в SKILL.md (інваріанти призначення скіла).
CANON = [
    "RLM",                       # сама ідея
    "диригент",                  # conductor role
    "найсильніш",                # conductor = strongest model
    "найдешевш",                 # workers = cheapest fit
    "Принцип #0",                # economy on process, not result
    "Plan-Execute-Verify-Replan",# control loop
    "REPLAN",                    # self-correction
    "план-перший",               # plan-first (not myopic)
    "ABORT",                     # budget ceiling behaviour
    "budget guard",              # cost governor
    "progressive disclosure",    # recipe loading
    "recipe",                    # recipe registry (Recipe Registry / recipe-template)
    "safety-compliance-gate",    # thin pointer
    "validation-mesh",           # delegation: validation
    "workflow-orchestration",    # delegation: topology
    "semantic-router",           # delegation: routing
    "Delegation Map",            # non-duplication contract
    "незалежний вердикт",        # independent-opinion mandate
]

def read_skill():
    with open(SKILL, encoding="utf-8") as f:
        return f.read()

def validate():
    text = read_skill()
    missing = [t for t in CANON if t.lower() not in text.lower()]
    if missing:
        print("GUARD FAIL — відсутні canonical terms:")
        for m in missing:
            print("  -", m)
        return 1
    # базові ліміти платформи
    n_lines = text.count("\n") + 1
    if n_lines >= 500:
        print(f"GUARD FAIL — SKILL.md {n_lines} рядків (>=500). Винеси в references/.")
        return 1
    print(f"GUARD OK — {len(CANON)} canonical terms присутні; SKILL.md {n_lines} рядків (<500).")
    return 0

def snapshot():
    os.makedirs(SNAP_DIR, exist_ok=True)
    text = read_skill()
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(SNAP_DIR, f"SKILL.{ts}.{h}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("SNAPSHOT:", os.path.relpath(path, HERE))
    return 0

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "--validate"
    if cmd == "--snapshot":
        sys.exit(snapshot())
    sys.exit(validate())
