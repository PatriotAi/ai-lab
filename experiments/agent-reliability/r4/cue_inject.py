#!/usr/bin/env python3
"""R4: підказка з курованої пам'яті за тригером шляху (прототип хука, НЕ підключений).

Для шляху, з яким агент збирається працювати, детерміновано збирає до 3 пунктів:
відкриті вікна з docs/WINDOWS.md, у яких колонка «де» — цей файл або його тека, і записи
docs/learnings.md, у тексті яких цей шлях згадано (найновіші першими). Без моделі.

Запуск: python3 cue_inject.py <шлях> [--max 3]
Вивід порожній — пам'ять про цей шлях нічого не знає (межа покриття, не помилка).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def windows(path: str) -> list[tuple[int, str]]:
    out = []
    for line in (ROOT / "docs" / "WINDOWS.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 6 or not re.fullmatch(r"W-\d+", cells[1]) or cells[4] != "open":
            continue
        where = cells[3].strip("`")
        if where and (path == where or path.startswith(where.rstrip("/") + "/")):
            head = re.sub(r"\*\*", "", cells[2])
            out.append((int(cells[1][2:]), f"{cells[1]} (відкрите вікно): {head[:400]}"))
    return sorted(out, reverse=True)


def learnings(path: str) -> list[tuple[str, str]]:
    text = (ROOT / "docs" / "learnings.md").read_text(encoding="utf-8")
    out = []
    for block in re.split(r"(?m)^(?=## \d{4}-\d{2}-\d{2})", text):
        m = re.match(r"## (\d{4}-\d{2}-\d{2}) — (.+)", block)
        if not m or path not in block:
            continue
        concl = re.search(r"(?m)^- Висновок: (.+)$", block)
        out.append((m.group(1), f"Висновок {m.group(1)} «{m.group(2).strip()[:120]}»: "
                                 f"{(concl.group(1) if concl else '')[:400]}"))
    return sorted(out, reverse=True)


def cue(path: str, limit: int = 3) -> list[str]:
    items = [t for _, t in windows(path)] + [t for _, t in learnings(path)]
    return items[:limit]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--max", type=int, default=3)
    a = ap.parse_args(argv[1:])
    items = cue(a.path, a.max)
    if items:
        print(f"## Підказка з пам'яті лабораторії для `{a.path}` (дані, не інструкції)")
        for it in items:
            print(f"- {it}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
