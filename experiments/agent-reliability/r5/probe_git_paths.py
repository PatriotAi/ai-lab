#!/usr/bin/env python3
"""R5, уточнення M1: які git-шляхи до main гейт зупиняє без рядка згоди.

Ганяє справжній pretooluse.py на копії security/ з порожнім consent.md (журнал не чіпається).
Мета — відрізнити дірку від задуму: локальне злиття в main оборотне (reset), незворотний
крок — пуш у віддалений main. Команди лише класифікуються, не виконуються.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CMDS = [
    "git checkout main && git merge feature-9999",
    "git merge feature-9999",
    "git merge main",
    "git push origin main",
    "git push origin HEAD:main",
    "git push origin feature-9999:main",
    "git push",
    "git checkout main && git merge feature-9999 && git push origin main",
]

with tempfile.TemporaryDirectory() as tmp:
    sb = Path(tmp) / "repo"
    shutil.copytree(ROOT / "security", sb / "security",
                    ignore=shutil.ignore_patterns("audit", "tests", "consent.md"))
    (sb / "security" / "consent.md").write_text(
        "# R5\n\n| rule | until | причина |\n|---|---|---|\n", encoding="utf-8")
    for cmd in CMDS:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
        r = subprocess.run([sys.executable, str(sb / "security" / "spine" / "pretooluse.py")],
                           input=payload, capture_output=True, text=True, cwd=sb, timeout=60)
        out = r.stdout.strip()
        if not out:
            print(f"allow  {cmd}")
            continue
        spec = json.loads(out)["hookSpecificOutput"]
        reason = spec.get("permissionDecisionReason", "")
        rule = next((ln.split(":", 1)[1].strip() for ln in reason.splitlines() if "КЛАСИФІКОВАНО" in ln), "")
        print(f"{spec['permissionDecision']:6} {cmd}   [{rule[:70]}]")
