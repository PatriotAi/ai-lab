#!/usr/bin/env python3
"""check-abstentions.py — абстенція `[?]` мусить називати, ЧОГО бракує.

НАВІЩО ОКРЕМО ВІД melania. `maintain.py verify` перевіряє теги доказовості лише
в секціях «Critical Facts» навичок. Але правило §10 CLAUDE.md діє на ВСІ мої
твердження — зокрема в `docs/`, `automations/`, `security/`. Без цієї перевірки
`[?]` у лабораторних документах трималось би на уважності, а такий крок тихо
порушується (Core Rule 15).

ЩО САМЕ ПЕРЕВІРЯЄТЬСЯ. Пункт списку, який **позначений** `[?]` — тобто тег стоїть
на початку пункту, як маркер твердження, — мусить містити «бракує:».

ЧОМУ САМЕ «НА ПОЧАТКУ». Перша версія шукала тег будь-де в пункті й одразу дала
дві хибні тривоги на власному ж брифінгу, де `[?]` **обговорюється** («тег `[?]`
(робоча назва) у Core Rule 14», «над-абстенція: все стає `[?]`»). Згадка тега —
не твердження з тегом; це той самий клас помилки «міряємо згадку замість дії»,
що й у безпековому гейті. Додатковий запобіжник: пункт, який перелічує теги
разом ([E]/[C]/[S] поруч), — визначення, не вживання.

ЧОГО ТУТ НЕ РОБИТЬСЯ. Скрипт не судить, чи абстенція доречна: guard проти
над-абстенції (доказ існує → це [E]) живе в `maintain.py`, бо вимагає резолву
шляхів у корені навички. Тут — лише «назви брак».

Запуск:
    python3 scripts/check-abstentions.py [корінь]
Код виходу: 0 — чисто · 1 — є абстенції без «бракує:» · 2 — помилка виклику.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Де шукаємо. melania-скіли свідомо поза межами: їх покриває maintain.py verify,
# і дублювання перевірки дало б два джерела правди для одного правила.
SCAN_DIRS = ("docs", "automations", "security", "experiments", "projects")
SCAN_FILES = ("CLAUDE.md", "README.md", "SECURITY.md")
# tests/ і сам цей скрипт містять ФІКСТУРИ з навмисно зламаними прикладами.
SKIP_PARTS = ("tests", ".git", "node_modules", "melania-skills-ecosystem")

OTHER_TAGS = re.compile(r"\[(?:E|C|S)\]")
ABSTAIN = re.compile(r"\[\?\]")
# Тег як МАРКЕР твердження: на початку пункту, можливо під жирним чи в лапках.
ABSTAIN_MARKER = re.compile(r"^\s*[-*+]\s*(?:[*_`]{1,3}\s*)?\[\?\]")
NEEDS = re.compile(r"бракує\s*:", re.I)


def bullets(text: str) -> list[str]:
    """Пункти списку разом із рядками-продовженнями.

    Продовження важливе: «бракує:» законно стоїть на наступному рядку того ж
    пункту, і порядкова перевірка дала б тут хибну тривогу.
    """
    out: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if re.match(r"^\s*[-*+] ", line):
            if current:
                out.append("\n".join(current))
            current = [line]
        elif current and (line.startswith(("  ", "\t")) or line.strip()):
            current.append(line)
        else:
            if current:
                out.append("\n".join(current))
            current = []
    if current:
        out.append("\n".join(current))
    return out


def problems(root: Path) -> list[str]:
    found: list[str] = []
    targets: list[Path] = [root / f for f in SCAN_FILES]
    for d in SCAN_DIRS:
        targets += sorted((root / d).rglob("*.md")) if (root / d).is_dir() else []
    for path in targets:
        if not path.is_file() or any(p in path.parts for p in SKIP_PARTS):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not ABSTAIN.search(text):
            continue
        for bullet in bullets(text):
            if not ABSTAIN_MARKER.match(bullet):  # згадка тега — не твердження з тегом
                continue
            if OTHER_TAGS.search(bullet):         # визначення тега, не вживання
                continue
            if NEEDS.search(bullet):
                continue
            rel = path.relative_to(root)
            found.append(f"{rel}: [?] без «бракує:» — {bullet.strip()[:90]}")
    return found


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[1]
    if not root.is_dir():
        print(f"check-abstentions: немає такої теки: {root}", file=sys.stderr)
        return 2
    found = problems(root)
    if found:
        print(f"🚩 абстенцій без «бракує:»: {len(found)}")
        for f in found:
            print(f"  ✗ {f}")
        print("\n  Абстенція мусить назвати, чого бракує у специфікації — "
              "інакше вона не підказує дії (CLAUDE.md §10).")
        return 1
    print("✅ усі абстенції [?] називають, чого бракує")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
