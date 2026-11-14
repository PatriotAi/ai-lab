#!/usr/bin/env python3
"""Реєстр проєкту для дерева виконавців (`rlm-harness/references/session-tree.md`).

Один JSON-файл на проєкт: задачі з lease (хто тримає, до коли), журнал КОЖНОЇ ітерації
(і провальної) та рішення кореня. Робить машинною перевіркою те, що інакше тримається на
уважності: дві сесії на одній задачі, «готово» без перевірки, мовчазне самолікування понад
бюджет. Лише stdlib, без мережі. Пише в реєстр — корінь; виконавці звітують, корінь вносить.

  run-ledger.py init   F --goal "…" [--max-iter 5]
  run-ledger.py claim  F TASK --by SESSION [--hours 4]      # lease; зайнята іншим — код 1
  run-ledger.py log    F TASK --status pass|fail --note "…"   # ітерація (і провальна)
  run-ledger.py done   F TASK --evidence "команда/шлях"      # лише після останньої pass
  run-ledger.py release F TASK
  run-ledger.py check  F [--now ISO]                          # код 1 при порушенні
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def now(arg: str | None = None) -> datetime:
    return datetime.fromisoformat(arg) if arg else datetime.now(timezone.utc)


def load(f: Path) -> dict:
    return json.loads(f.read_text(encoding="utf-8"))


def save(f: Path, d: dict) -> None:
    f.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def task(d: dict, name: str) -> dict:
    return d["tasks"].setdefault(name, {"lease": None, "iterations": [], "done": None})


def problems(d: dict, at: datetime) -> list[str]:
    out = []
    cap = d.get("max_iter", 5)
    for name, t in d["tasks"].items():
        its = t["iterations"]
        fails_tail = 0
        for it in reversed(its):
            if it["status"] != "fail":
                break
            fails_tail += 1
        if t["done"]:
            if not its or its[-1]["status"] != "pass":
                out.append(f"{name}: позначено «готово», але остання ітерація не pass (звіт ≠ доказ)")
            if not t["done"].get("evidence"):
                out.append(f"{name}: «готово» без вказівника на доказ")
        elif fails_tail >= cap:
            out.append(f"{name}: {fails_tail} провалів поспіль ≥ бюджету {cap} — ескалація до стовбура, не нова спроба")
        lease = t["lease"]
        if lease and not t["done"] and datetime.fromisoformat(lease["until"]) < at:
            out.append(f"{name}: lease {lease['by']} прострочено ({lease['until']}) — звільнити або продовжити")
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["init", "claim", "log", "done", "release", "check"])
    ap.add_argument("file", type=Path)
    ap.add_argument("task", nargs="?")
    ap.add_argument("--goal"); ap.add_argument("--max-iter", type=int, default=5)
    ap.add_argument("--by"); ap.add_argument("--hours", type=float, default=4)
    ap.add_argument("--status", choices=["pass", "fail"]); ap.add_argument("--note", default="")
    ap.add_argument("--evidence"); ap.add_argument("--now")
    a = ap.parse_args(argv)
    at = now(a.now)
    if a.cmd == "init":
        if a.file.exists():
            print(f"реєстр уже існує: {a.file}", file=sys.stderr); return 2
        save(a.file, {"goal": a.goal or "", "max_iter": a.max_iter, "created": at.isoformat(), "tasks": {}})
        return 0
    d = load(a.file)
    if a.cmd == "check":
        ps = problems(d, at)
        for p in ps:
            print(f"✗ {p}")
        if not ps:
            print(f"✅ реєстр узгоджений: {len(d['tasks'])} задач")
        return 1 if ps else 0
    if not a.task:
        print("потрібна назва задачі", file=sys.stderr); return 2
    t = task(d, a.task)
    if a.cmd == "claim":
        lease = t["lease"]
        if lease and lease["by"] != a.by and datetime.fromisoformat(lease["until"]) >= at and not t["done"]:
            print(f"✗ {a.task} тримає {lease['by']} до {lease['until']} — дубль заборонено", file=sys.stderr)
            return 1
        t["lease"] = {"by": a.by, "until": (at + timedelta(hours=a.hours)).isoformat()}
    elif a.cmd == "log":
        if not a.status:
            print("потрібен --status", file=sys.stderr); return 2
        t["iterations"].append({"at": at.isoformat(), "status": a.status, "note": a.note})
    elif a.cmd == "done":
        if not t["iterations"] or t["iterations"][-1]["status"] != "pass" or not a.evidence:
            print(f"✗ {a.task}: «готово» лише після останньої pass-ітерації і з --evidence", file=sys.stderr)
            return 1
        t["done"] = {"at": at.isoformat(), "evidence": a.evidence}
    elif a.cmd == "release":
        t["lease"] = None
    save(a.file, d)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
