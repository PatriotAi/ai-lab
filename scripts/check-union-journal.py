#!/usr/bin/env python3
"""check-union-journal.py — union-злиття журналу лишається безпечним.

НАВІЩО. `.gitattributes` вмикає вбудований драйвер `merge=union` для журналів, куди
лише дописують (`docs/learnings.md`). Виміряно на історії репозиторію: 13 із 22
конфліктних злиттів були саме в ньому, і union розв'язує всі 13 без втрати запису
(docs/reviews/2026-10-09-git-substrate-audit.md). Ціна union — він НІКОЛИ не показує
конфлікт: якщо обидві гілки змінили ОДИН старий рядок, у файлі тихо залишаться обидві
версії. Скрипт ловить саме цей клас, а також ризик самого файла атрибутів.

ЩО ПЕРЕВІРЯЄ.
 1. `.gitattributes` містить лише коментарі, порожні рядки й `<шлях> merge=union`.
    Будь-що інше (filter, diff, binary, linguist-*, export-*) змінює злиття чи ховає
    зміни від рев'ю — це рішення власника, не побічний ефект.
 2. Кожен union-шлях існує (інакше атрибут мертвий) і є журналом записів
    «## YYYY-MM-DD — …» (union безпечний лише для дописування записів).
 3. У журналі заголовки записів не повторюються, а в одному записі не більше одного
    рядка «- Дія:» — це найчастіше дописуваний старий рядок (позначки «Змержено …»),
    і саме його дубль залишив би union після паралельних правок.

Запуск:  python3 scripts/check-union-journal.py [корінь]
Код виходу: 0 — чисто · 1 — знахідки · 2 — помилка виклику.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ALLOWED = re.compile(r"^(\S+)\s+merge=union\s*$")
ENTRY = re.compile(r"(?m)^(?=## \d{4}-\d{2}-\d{2}\b)")
HEAD = re.compile(r"## (\d{4}-\d{2}-\d{2}[^\n]*)")
ACTION = re.compile(r"(?m)^- Дія:")


def root_of(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return Path(r.stdout.strip() or ".")


def journal_problems(path: Path, rel: str) -> list[str]:
    text = path.read_text(encoding="utf-8")
    entries = [e for e in ENTRY.split(text) if HEAD.match(e)]
    if not entries:
        return [f"{rel}: union дозволено лише для журналів записів «## YYYY-MM-DD — …», а тут їх немає"]
    out, seen = [], {}
    for e in entries:
        title = HEAD.match(e).group(1).strip()
        if title in seen:
            out.append(f"{rel}: заголовок запису повторюється — «{title[:70]}» (слід union-злиття двох версій?)")
        seen[title] = True
        n = len(ACTION.findall(e))
        if n > 1:
            out.append(f"{rel}: у записі «{title[:70]}» {n} рядки «- Дія:» — union лишив обидві версії "
                       "зміненого рядка; звести вручну")
    return out


def main() -> int:
    if len(sys.argv) > 2:
        print("Використання: python3 scripts/check-union-journal.py [корінь]", file=sys.stderr)
        return 2
    root = root_of(sys.argv[1] if len(sys.argv) == 2 else None)
    attrs = root / ".gitattributes"
    if not attrs.exists():
        print("ℹ️ .gitattributes немає — union-журналів немає, перевіряти нічого")
        return 0
    problems, journals = [], []
    for no, raw in enumerate(attrs.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = ALLOWED.match(line)
        if not m:
            problems.append(f".gitattributes:{no}: заборонений атрибут «{line[:80]}» — дозволено лише "
                            "«<шлях> merge=union» (решта змінює злиття чи ховає зміни від рев'ю)")
            continue
        journals.append(m.group(1))
    for rel in journals:
        p = root / rel
        if any(ch in rel for ch in "*?[") or not p.is_file():
            problems.append(f".gitattributes: union-шлях «{rel}» не є наявним файлом (шаблони й мертві шляхи заборонено)")
            continue
        problems += journal_problems(p, rel)
    if problems:
        print("❌ union-журнал небезпечний:")
        for pr in problems:
            print(f"  ✗ {pr}")
        return 1
    print(f"✅ union-журнали безпечні ({', '.join(journals) or 'немає'}): атрибути з дозволеного переліку, "
          "заголовки унікальні, рядок «Дія» — один на запис")
    return 0


if __name__ == "__main__":
    sys.exit(main())
