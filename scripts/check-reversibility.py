#!/usr/bin/env python3
"""check-reversibility.py — рішення `one-way` мусить мати записане рішення власника.

НАВІЩО. Рівні ризику `R0–R4` судять **дію в момент виконання** (пуш, merge,
секрети). Але найдорожчі помилки — не в діях, а в **рішеннях**, ухвалених раніше:
формат на диску, публічний контракт, прив'язка до сервісу. Такі двері («one-way»)
гейт дій не бачить: сам запис файлу — звичайний R1.

Тому таксономія рішень (`docs/methodology.md`, `templates/experiment.md`):
    reversible  відкат локальний і дешевий            → нічого не потрібно
    costly      відкат чіпає багато місць             → позначити, не блокувати
    one-way     відкат = міграція чи зламаний контракт → РІШЕННЯ ВЛАСНИКА до реалізації

ЩО ПЕРЕВІРЯЄТЬСЯ ТУТ. Документ, який позначив рішення як `one-way`, мусить у тому
ж пункті (або в наступних рядках того ж пункту) містити рішення власника:
«рішення власника», «згода власника» або «власник обрав/вирішив/дозволив».
Інакше позначка `one-way` залишається словом — тобто рівно тим класом, який
Core Rule 15 називає «звіт замість доказу».

ПРОТИ ІНФЛЯЦІЇ. Скрипт свідомо НЕ вимагає, щоб рішення взагалі були позначені:
правило «сумніваєшся — став reversible» важливіше за покриття. Документ, де все
`one-way`, ніхто не читає, і він не гейтить нічого.

ЧОГО ТУТ НЕ РОБИТЬСЯ. Не судить, чи рейтинг правильний: це рішення людини.
Перевіряється лише те, що на найсуворішому рейтингу є слід рішення власника.

Запуск:
    python3 scripts/check-reversibility.py [корінь]
Код виходу: 0 — чисто · 1 — `one-way` без рішення власника · 2 — помилка виклику.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCAN_DIRS = ("docs", "experiments", "projects", "automations", "security")
SCAN_FILES = ("CLAUDE.md", "README.md")
# tests/ і templates/ містять ФІКСТУРИ та порожні заготовки з прикладами рейтингів.
SKIP_PARTS = ("tests", "templates", ".git", "node_modules", "melania-skills-ecosystem")

# Позначка як МАРКЕР рішення, а не згадка в прозі: `one-way` у беках або лапках
# після слова «незворотність»/«reversibility», або на початку пункту.
MARKER = re.compile(
    r"(?:незворотн\w*|reversibilit\w*)\s*[:=]\s*[`\"']?one-way"
    r"|^\s*[-*+]\s*(?:[*_`]{1,3}\s*)?one-way\b",
    re.I | re.M)
OWNER = re.compile(
    r"рішення\s+власник|згод[аи]\s+власник|власник\s+(?:обрав|вирішив|дозволив|схвалив)",
    re.I)


def bullets(text: str) -> list[str]:
    """Пункти списку з рядками-продовженнями (рішення власника буває нижче)."""
    out: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if re.match(r"^\s*[-*+] ", line) or re.match(r"^\s*\d+\. ", line):
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
        if (root / d).is_dir():
            targets += sorted((root / d).rglob("*.md"))
    for path in targets:
        if not path.is_file() or any(p in path.parts for p in SKIP_PARTS):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not MARKER.search(text):
            continue
        for bullet in bullets(text):
            if not MARKER.search(bullet):
                continue
            if OWNER.search(bullet):
                continue
            found.append(f"{path.relative_to(root)}: one-way без рішення власника "
                         f"— {bullet.strip()[:90]}")
    return found


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[1]
    if not root.is_dir():
        print(f"check-reversibility: немає такої теки: {root}", file=sys.stderr)
        return 2
    found = problems(root)
    if found:
        print(f"🚩 рішень `one-way` без рішення власника: {len(found)}")
        for f in found:
            print(f"  ✗ {f}")
        print("\n  Двері в один бік проходять із рішенням власника, ухваленим ДО "
              "реалізації. Якщо рішення було — назви його в тому ж пункті.")
        return 1
    print("✅ кожне рішення `one-way` має записане рішення власника")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
