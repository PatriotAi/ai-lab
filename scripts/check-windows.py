#!/usr/bin/env python3
"""check-windows.py — реєстр «розбитих вікон»: облік боргу, який видно на видачі.

НАВІЩО. Борг лабораторії фіксувався прозою в `docs/learnings.md` і 🟡-статусами
`docs/PLAN.md`. Це чесно, але **не гейт**: ніщо не заважало віддати роботу з
відкритим боргом, і «закрити борг хвилі» доводилось робити окремим заходом.
Реєстр (`docs/WINDOWS.md`) робить борг перелічуваним, а ця перевірка — машинним.

ДВА РЕЖИМИ (свідомо).
    без прапорця  — облік: звітує, код 0, поки сам реєстр коректний;
    --strict      — гейт: ненульовий код, якщо є хоч одне вікно `open`.

Чому не «завжди блокувати»: гейт, який червоніє на першому ж прогоні через
борг, що існував і до нього, вчить себе обходити — а обхід не лишає сліду.
Перемикання на блокування — рішення власника (`docs/WINDOWS.md`).

ЩО ВВАЖАЄТЬСЯ ПОЛОМКОЮ САМОГО РЕЄСТРУ (код 2, у будь-якому режимі):
    · лічильник у першому рядку не збігається з фактом (правило anti-stale);
    · `waived` без причини (≥20 символів) або без дати — тоді це не рішення,
      а забудькуватість, яку просто назвали рішенням;
    · `open`/`waived` без вказівника на місце, яке РЕАЛЬНО існує на диску —
      вікно без адреси неможливо ні знайти, ні закрити (той самий принцип, що
      для `[E]`: формат вказівника ще не доказ);
    · невідомий стан (не `open`/`fixed`/`waived`).

Запуск:
    python3 scripts/check-windows.py [--strict] [корінь]
Коди виходу: 0 — реєстр коректний (і, у --strict, відкритих вікон немає)
             1 — є відкриті вікна (лише --strict)
             2 — реєстр зламаний або відсутній
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REGISTER = Path("docs") / "WINDOWS.md"
STATES = ("open", "fixed", "waived")
COUNTER = re.compile(r"<!--\s*ВІДКРИТИХ ВІКОН:\s*(\d+)\s*-->")
MIN_REASON = 20


def parse(text: str) -> tuple[list[dict], list[str]]:
    """Розбирає таблицю реєстру. Повертає (рядки, поломки розбору)."""
    rows: list[dict] = []
    broken: list[str] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        if cells[0] in ("id", "---") or set(cells[0]) <= {"-", ":"}:
            continue
        if not re.match(r"^W-\d+$", cells[0]):
            broken.append(f"невідомий ідентифікатор вікна: «{cells[0]}» (очікується W-<число>)")
            continue
        rows.append({
            "id": cells[0], "what": cells[1], "where": cells[2],
            "state": cells[3].lower(), "note": cells[4],
        })
    return rows, broken


def problems(root: Path, rows: list[dict], text: str) -> list[str]:
    found: list[str] = []
    for row in rows:
        if row["state"] not in STATES:
            found.append(f"{row['id']}: невідомий стан «{row['state']}» "
                         f"(очікується {'/'.join(STATES)})")
            continue
        # Адреса вікна мусить існувати — інакше його не знайти й не закрити.
        if row["state"] in ("open", "waived"):
            # УВАГА: `lstrip("./")` тут був би дефектом — він зрізає НАБІР
            # символів, тож `.pre-commit-config.yaml` ставав
            # `pre-commit-config.yaml` і перевірка існування падала на
            # правильному шляху. Спіймано першим же прогоном на власному
            # реєстрі; той самий клас помилки, що й у токені шляху гейта
            # кількома годинами раніше. Зрізаємо саме ПРЕФІКС «./».
            where = re.sub(r"^\./", "", row["where"].strip("`"))
            if not where or not (root / where).exists():
                found.append(f"{row['id']}: вказівник «{row['where']}» не існує на диску")
        # `waived` — це РІШЕННЯ, тож мусить мати причину й дату.
        if row["state"] == "waived":
            note = row["note"]
            if len(note) < MIN_REASON:
                found.append(f"{row['id']}: waived без причини (≥{MIN_REASON} символів) — "
                             f"без неї це забудькуватість, яку назвали рішенням")
            if not re.search(r"\d{4}-\d{2}-\d{2}", note):
                found.append(f"{row['id']}: waived без дати рішення")
    # Лічильник рахує скрипт, не людина.
    match = COUNTER.search(text)
    open_count = sum(1 for r in rows if r["state"] == "open")
    if not match:
        found.append("у першому рядку немає лічильника "
                     "«<!-- ВІДКРИТИХ ВІКОН: N -->»")
    elif int(match.group(1)) != open_count:
        found.append(f"лічильник у файлі ({match.group(1)}) != факт ({open_count})")
    return found


def fix_counter(path: Path, text: str, rows: list[dict]) -> str:
    """Переписати лічильник фактом. Злиття двох гілок, кожна з яких додала вікно,
    тихо лишає «16 → 17» замість 18 (тричі за історію PR #94) — виправлення руками
    щоразу трималось на уважності. Лише лічильник: решту поломок лагодить людина."""
    open_count = sum(1 for r in rows if r["state"] == "open")
    line = f"<!-- ВІДКРИТИХ ВІКОН: {open_count} -->"
    new = COUNTER.sub(line, text, count=1) if COUNTER.search(text) else f"{line}\n{text}"
    if new != text:
        path.write_text(new, encoding="utf-8")
        print(f"check-windows: лічильник виправлено → {open_count}")
    return new


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    fix = "--fix-counter" in argv
    rest = [a for a in argv[1:] if a not in ("--strict", "--fix-counter")]
    root = Path(rest[0]) if rest else Path(__file__).resolve().parents[1]
    path = root / REGISTER
    if not path.is_file():
        print(f"check-windows: реєстру немає: {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8", errors="replace")
    rows, broken = parse(text)
    # Не правимо лічильник зламаного реєстру: число з битих рядків — теж неправда.
    if fix and not broken and all(r["state"] in STATES for r in rows):
        text = fix_counter(path, text, rows)
    issues = broken + problems(root, rows, text)
    if issues:
        print(f"🚩 реєстр зламаний — {len(issues)}:")
        for i in issues:
            print(f"  ✗ {i}")
        return 2

    opened = [r for r in rows if r["state"] == "open"]
    waived = [r for r in rows if r["state"] == "waived"]
    fixed = [r for r in rows if r["state"] == "fixed"]
    print(f"вікна: відкритих {len(opened)} · свідомо не закриваємо {len(waived)} "
          f"· закрито {len(fixed)}")
    for r in opened:
        print(f"  ○ {r['id']} — {r['what'][:90]} ({r['where']})")
    if not opened:
        print("✅ відкритих вікон немає")
    elif strict:
        print("\n  Ці вікна треба або закрити, або свідомо перевести у `waived` "
              "із записаною причиною. Мовчки віддавати роботу з ними — не варіант.")
        return 1
    else:
        print("\n  Режим обліку: код 0. Гейт перед видачею називає ці вікна у здачі "
              "(`--strict` дає ненульовий код).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
