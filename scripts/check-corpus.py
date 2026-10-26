#!/usr/bin/env python3
"""check-corpus.py — корпус інцидентів відповідає кодовій книзі.

НАВІЩО. Корпус `corpus.jsonl` (дослідження «Вивірений розвиток», Ф1) кодують два незалежні
агенти, а з нього рахуються H1a і H4. Запис із кодом, якого немає в кодовій книзі, дубль `id`
чи неіснуюча дата тихо псують підрахунок, і в звіті цього не видно (Core Rule 15).

ЄДИНЕ ДЖЕРЕЛО. Поля й дозволені значення скрипт читає з таблиць кодової книги в
`experiments/verified-development/preregistration.md` (розділ «Кодова книга v1»): таблиця
«Структура запису» дає поля, їхні типи й обов'язковість, а таблиці «Поле `X`» — коди. Власного
списку кодів тут немає, тож кодова книга й перевірка не можуть розійтися (крок Ф0.5).

Типи в таблиці структури: `id` (`vd-NNN`), `date` (`YYYY-MM-DD`, справжня дата), `text`
(непорожній рядок), `source` (вказівник, що існує: `PR #N`, коміт, що є в історії, або шлях
у репо, можна з `#фрагментом`), `code` (значення з таблиці цього поля), `codes:<поле>` (список
кодів із таблиці іншого поля), `int?` (ціле ≥ 0 або `null`), `indicators` (список з `I1`–`I6`),
`names` / `names:N` (список непорожніх імен; з `:N` — щонайменше N різних). Обов'язковість —
лише `так` або `ні`: описка там мовчки зробила б поле необов'язковим (рев'ю Codex до PR #103).

Запуск:
    python3 scripts/check-corpus.py [корінь] [--corpus ШЛЯХ] [--codebook ШЛЯХ]
Код виходу: 0 — чисто (або корпусу ще нема, перевірено лише кодову книгу) ·
1 — у корпусі є порушення · 2 — перевірити неможливо (кодової книги нема чи вона неповна).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

CODEBOOK = "experiments/verified-development/preregistration.md"
CORPUS = "experiments/verified-development/corpus.jsonl"
STRUCTURE = "### Структура запису"
FIELD_HEADING = re.compile(r"^### Поле `([a-z_]+)`")
CELL_CODE = re.compile(r"^`([^`]+)`$")
ID = re.compile(r"^vd-\d{3,}$")
INDICATORS = {f"I{n}" for n in range(1, 7)}
TYPES = re.compile(r"^(id|date|text|source|code|codes:[a-z_]+|int\?|indicators|names(?::\d+)?)$")
PR = re.compile(r"^PR #\d+$")
COMMIT = re.compile(r"^[0-9a-f]{7,40}$")


def table_rows(lines: list[str], start: int) -> list[list[str]]:
    """Рядки таблиці після заголовка `start` до наступного заголовка; без шапки й розділювача."""
    rows = []
    for ln in lines[start + 1:]:
        if ln.startswith("#"):
            break
        if not ln.lstrip().startswith("|") or set(ln.replace("|", "").strip()) <= set("-: "):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if CELL_CODE.match(cells[0]):
            rows.append(cells)
    return rows


def parse_codebook(text: str) -> tuple[dict[str, tuple[str, bool]], dict[str, set[str]], list[str]]:
    """Поля {назва: (тип, обов'язкове)}, коди {поле: {коди}} і вади самої кодової книги."""
    lines = text.splitlines()
    fields: dict[str, tuple[str, bool]] = {}
    codes: dict[str, set[str]] = {}
    bad_required: list[str] = []
    for i, ln in enumerate(lines):
        if ln.strip() == STRUCTURE:
            for cells in table_rows(lines, i):
                if len(cells) >= 3:
                    name = CELL_CODE.match(cells[0]).group(1)
                    fields[name] = (cells[1], cells[2] == "так")
                    if cells[2] not in ("так", "ні"):
                        bad_required.append(f"поле `{name}`: обов'язковість «{cells[2]}» — має бути «так» або «ні»")
        m = FIELD_HEADING.match(ln)
        if m:
            codes[m.group(1)] = {CELL_CODE.match(c[0]).group(1) for c in table_rows(lines, i)}
    flaws = list(bad_required)
    for name, (kind, _) in fields.items():
        if not TYPES.match(kind):
            flaws.append(f"поле `{name}`: невідомий тип «{kind}»")
        elif kind == "code" and not codes.get(name):
            flaws.append(f"поле `{name}`: тип code, але таблиці «Поле `{name}`» нема або вона порожня")
        elif kind.startswith("codes:") and not codes.get(kind.split(":", 1)[1]):
            flaws.append(f"поле `{name}`: посилається на таблицю «Поле `{kind.split(':', 1)[1]}`», якої нема")
    return fields, codes, flaws


def valid_date(value: object) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def source_error(value: object, root: Path) -> str | None:
    """Вказівник на доказ, що існує: `PR #N`, коміт з історії або шлях у репо (рев'ю Codex до PR #103)."""
    if not isinstance(value, str) or not value.strip():
        return "очікувано вказівник: шлях у репо, `PR #N` або коміт"
    if PR.match(value):
        return None
    if COMMIT.match(value):
        run = subprocess.run(["git", "cat-file", "-e", f"{value}^{{commit}}"], cwd=root,
                             capture_output=True, text=True)
        return None if run.returncode == 0 else f"коміту {value} нема в історії репо"
    path = value.split("#", 1)[0]
    if Path(path).is_absolute() or ".." in Path(path).parts or not (root / path).exists():
        return f"«{value}» — не `PR #N`, не коміт і не наявний шлях у репо"
    return None


def type_error(value: object, kind: str, field: str, codes: dict[str, set[str]],
               root: Path) -> str | None:
    """Опис порушення типу або None, якщо значення відповідає типу з кодової книги."""
    if kind == "source":
        return source_error(value, root)
    if kind == "id":
        return None if isinstance(value, str) and ID.match(value) else "очікувано `vd-NNN`"
    if kind == "date":
        return None if valid_date(value) else "очікувано справжню дату YYYY-MM-DD"
    if kind == "text":
        return None if isinstance(value, str) and value.strip() else "очікувано непорожній рядок"
    if kind == "code":
        return None if value in codes[field] else f"коду «{value}» нема в таблиці «Поле `{field}`»"
    if kind.startswith("codes:"):
        table = kind.split(":", 1)[1]
        if not isinstance(value, list):
            return "очікувано список"
        bad = [v for v in value if v not in codes[table]]
        return f"кодів {bad} нема в таблиці «Поле `{table}`»" if bad else None
    if kind == "int?":
        ok = value is None or (isinstance(value, int) and not isinstance(value, bool) and value >= 0)
        return None if ok else "очікувано ціле ≥ 0 або null"
    if kind == "indicators":
        ok = isinstance(value, list) and all(v in INDICATORS for v in value)
        return None if ok else "очікувано список з I1–I6"
    if kind.startswith("names"):
        need = int(kind.split(":", 1)[1]) if ":" in kind else 1
        ok = isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)
        if not ok or len(set(value)) < need:
            return f"очікувано щонайменше {need} різн{'е ім’я' if need == 1 else 'і імені'}"
        return None
    return f"невідомий тип «{kind}»"


def check_corpus(text: str, fields: dict[str, tuple[str, bool]],
                 codes: dict[str, set[str]], root: Path) -> list[str]:
    errors: list[str] = []
    seen: dict[str, int] = {}
    for n, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"рядок {n}: не JSON ({exc.msg})")
            continue
        if not isinstance(rec, dict):
            errors.append(f"рядок {n}: очікувано JSON-об'єкт")
            continue
        for name in sorted(set(rec) - set(fields)):
            errors.append(f"рядок {n}: поле `{name}` поза кодовою книгою")
        for name, (kind, required) in fields.items():
            if name not in rec:
                if required:
                    errors.append(f"рядок {n}: бракує обов'язкового поля `{name}`")
                continue
            err = type_error(rec[name], kind, name, codes, root)
            if err:
                errors.append(f"рядок {n}: `{name}` — {err}")
        rid = rec.get("id")
        if isinstance(rid, str):
            if rid in seen:
                errors.append(f"рядок {n}: `id` {rid} уже був у рядку {seen[rid]}")
            seen.setdefault(rid, n)
        others = rec.get("detectors_other")
        if isinstance(others, list) and rec.get("detector") in others:
            errors.append(f"рядок {n}: `detectors_other` містить перший виявлювач `{rec['detector']}`")
    return errors


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Корпус інцидентів відповідає кодовій книзі.")
    ap.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--corpus", help=f"шлях до корпусу (типово {CORPUS})")
    ap.add_argument("--codebook", help=f"шлях до кодової книги (типово {CODEBOOK})")
    args = ap.parse_args(argv[1:])
    root = Path(args.root)
    book = Path(args.codebook) if args.codebook else root / CODEBOOK
    corpus = Path(args.corpus) if args.corpus else root / CORPUS
    if not book.is_file():
        print(f"⊘ НЕ ГАНЯЛОСЬ: кодової книги нема — {book}")
        return 2
    fields, codes, flaws = parse_codebook(book.read_text(encoding="utf-8", errors="replace"))
    if not fields:
        print(f"⊘ НЕ ГАНЯЛОСЬ: у {book} нема таблиці «{STRUCTURE[4:]}» — перевіряти нема з чим")
        return 2
    if flaws:
        for f in flaws:
            print(f"  ✗ кодова книга: {f}")
        print("⊘ НЕ ГАНЯЛОСЬ: кодова книга неповна — спершу виправ її")
        return 2
    if not corpus.is_file():
        print(f"✅ кодова книга цілісна ({len(fields)} полів); корпусу ще нема ({corpus.name}) — "
              f"перевірено лише кодову книгу")
        return 0
    errors = check_corpus(corpus.read_text(encoding="utf-8", errors="replace"), fields, codes, root)
    for e in errors[:30]:
        print(f"  ✗ {e}")
    if len(errors) > 30:
        print(f"  … і ще {len(errors) - 30}")
    if errors:
        print(f"\n🚩 корпус не відповідає кодовій книзі: {len(errors)} порушень")
        return 1
    print(f"✅ корпус відповідає кодовій книзі ({len(fields)} полів)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
