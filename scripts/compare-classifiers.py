#!/usr/bin/env python3
"""compare-classifiers.py — дві версії класифікатора на РЕАЛЬНОМУ корпусі дій.

Навіщо: стенд перевіряє приклади, які автор придумав; корпус — дії, які агент
справді виконував. Стандарт дому для кожної зміни `security/spine/classify.py`
(learnings 2026-10-18): старий і новий класифікатор на корпусі реальних дій
сесії, і кожна зміна рівня має бути запланованою. 2026-10-18 так знайдено, що
рівно одна з 161 дії змінила рівень — та сама хибна тривога, яку й виправляли.
До 2026-10-23 скрипт жив лише в тимчасовій теці сесії.

Корпус — виклики інструментів із транскрипту Claude Code (JSONL; повні входи,
а не обрізані цілі з журналу гейта). Вміст Write/Edit відкидається: класифікатор
його не читає. Кожна версія працює в ОКРЕМОМУ процесі — модулі не змішуються.

Запуск:
  python3 scripts/compare-classifiers.py <старий_корінь> <новий_корінь> <транскрипт.jsonl>
  (корінь — тека, де лежать security/spine/classify.py і security/policy.toml;
   стару версію зручно дістати: git worktree add /tmp/old <коміт>)
Код виходу (як у diff): 0 — змін рівня немає · 1 — є зміни (надруковано) · 2 — помилка.
"""
from __future__ import annotations

import json
import subprocess
import sys

TOOLS = ("Bash", "Read", "Write", "Edit", "Grep", "Glob")
DROP = ("content", "new_string", "old_string")

WORKER = r'''
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1] + "/security/spine")
import classify as c
root = Path(sys.argv[2])
pol = c.load_policy(Path(sys.argv[1]))
out = []
for tool, inp in json.load(sys.stdin):
    try:
        out.append(c.classify(tool, inp, root=root, policy=pol).level)
    except Exception as e:
        out.append("ERR:" + type(e).__name__)
json.dump(out, sys.stdout)
'''


def corpus(path: str) -> list[tuple[str, dict]]:
    items = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            msg = rec.get("message") if isinstance(rec, dict) else None
            content = msg.get("content") if isinstance(msg, dict) else None
            if not isinstance(content, list):
                continue
            for block in content:
                if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                    continue
                name, inp = block.get("name", ""), block.get("input") or {}
                if name in TOOLS or name.startswith("mcp__"):
                    items.append((name, {k: v for k, v in inp.items() if k not in DROP}))
    return items


def levels(root: str, items: list, repo: str) -> list[str]:
    res = subprocess.run([sys.executable, "-I", "-c", WORKER, root, repo],
                         input=json.dumps(items), capture_output=True, text=True)
    if res.returncode:
        print(f"  ❌ класифікатор у {root} впав: {res.stderr[-400:]}", file=sys.stderr)
        raise SystemExit(2)
    return json.loads(res.stdout)


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__.split("Запуск:")[1].split("Код виходу")[0].strip(), file=sys.stderr)
        return 2
    old_root, new_root, transcript = argv[1:]
    items = corpus(transcript)
    if not items:
        # Порожній корпус нічого не доводить — це помилка, а не «змін немає».
        print(f"  ❌ у {transcript} не знайдено жодного виклику інструмента", file=sys.stderr)
        return 2
    old, new = levels(old_root, items, new_root), levels(new_root, items, new_root)
    changed = [(i, o, n) for i, (o, n) in enumerate(zip(old, new)) if o != n]
    print(f"корпус: {len(items)} дій · змін рівня: {len(changed)}")
    for i, o, n in changed:
        tool, inp = items[i]
        text = inp.get("command") or inp.get("file_path") or json.dumps(inp, ensure_ascii=False)
        print(f"  {o} → {n}  [{tool}] {text[:110]!r}")
    return 1 if changed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
