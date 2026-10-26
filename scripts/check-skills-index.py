#!/usr/bin/env python3
"""check-skills-index.py — індекс `skills/README.md` мусить збігатися з диском.

НАВІЩО. «Активні навички» у `skills/README.md` — рукописний перелік, а каталог
`.claude/skills/` змінюється окремими PR. Аудит 2026-10-26 знайшов, що
`gmi-audit` існує на диску й роздається в бандлі `ai-lab-workflows`, але в
індексі його нема — і той самий файл стверджує «усі активні». Перелік тримався
на уважності, тож тихо розійшовся (Core Rule 15, CLAUDE.md §7).

ЩО ПЕРЕВІРЯЄТЬСЯ. Лабораторна навичка — СПРАВЖНЯ тека (не симлінк) у
`.claude/skills/`. Симлінки ведуть у `melania-skills-ecosystem/` і мають
власний облік (`MANIFEST`, `maintain.py verify`), тому тут не рахуються.
Пункт індексу — рядок списку БЕЗ відступу під заголовком «## Активні навички»,
що починається з назви в зворотних лапках; вкладені підпункти й рядки в
блоках коду ``` пунктами не є. Падіння:
  - навичка є на диску, але не в індексі;
  - пункт є в індексі, але лабораторної теки нема (або це симлінк melania);
  - тека в `.claude/skills/` без `SKILL.md` — це не навичка, а поломка.

Запуск:
    python3 scripts/check-skills-index.py [корінь]
Код виходу: 0 — збігається · 1 — розбіжність · 2 — помилка виклику.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HEADING = re.compile(r"^##\s+Активні навички\s*$")
NEXT_HEADING = re.compile(r"^##\s")
ITEM = re.compile(r"^[-*+]\s*`([^`]+)`")
FENCE = re.compile(r"^\s*(```|~~~)")


def indexed(text: str) -> set[str] | None:
    names: set[str] = set()
    inside = in_fence = False
    for line in text.splitlines():
        if HEADING.match(line):
            inside = True
            continue
        if not inside:
            continue
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if NEXT_HEADING.match(line):
            break
        if m := ITEM.match(line):
            names.add(m.group(1))
    return names if inside else None


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    base = root / ".claude" / "skills"
    readme = root / "skills" / "README.md"
    try:
        text = readme.read_text(encoding="utf-8")
        entries = list(base.iterdir())
    except (OSError, UnicodeDecodeError) as exc:
        print(f"помилка: не прочитати .claude/skills/ або skills/README.md у {root}: {exc}", file=sys.stderr)
        return 2
    listed = indexed(text)
    if listed is None:
        print("помилка: у skills/README.md нема заголовка «## Активні навички»", file=sys.stderr)
        return 2

    linked = {d.name for d in entries if d.is_symlink()}
    real = [d for d in entries if d.is_dir() and not d.is_symlink()]
    present = {d.name for d in real if (d / "SKILL.md").is_file()}
    broken = sorted(d.name for d in real if not (d / "SKILL.md").is_file())

    missing = sorted(present - listed)
    phantom = sorted(listed - present - set(broken))
    for name in broken:
        print(f"тека без SKILL.md: .claude/skills/{name}/ — не навичка; додай SKILL.md або прибери теку")
    for name in missing:
        print(f"нема в індексі: `{name}` є в .claude/skills/, але не в skills/README.md")
    for name in phantom:
        if name in linked:
            print(f"не лабораторна навичка: `{name}` — симлінк melania, її облік у MANIFEST, не в цьому індексі")
        else:
            print(f"привид в індексі: `{name}` є в skills/README.md, але теки .claude/skills/{name}/ нема")
    if broken or missing or phantom:
        return 1
    print(f"індекс навичок збігається з диском: {len(present)} лабораторних навичок")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
