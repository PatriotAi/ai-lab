#!/usr/bin/env python3
"""Гейт синхронності переносного стандарту з CLAUDE.md.

Read-only. Exit 0 — синхронно · 1 — розбіжність · 2 — перевірити неможливо
(немає секції/маркерів: це НЕ «ок» — порожній зріз не доводить чистоти).

НАВІЩО. `CLAUDE.md` і хуки діють лише в сесіях Claude Code цього репо. Для чатів
claude.ai та інших репо є версіонований зріз — `docs/portable-standard.md`. Без
перевірки він мовчки відстає від канону (дрейф «документ ≠ реальність», CLAUDE.md §7).

ЩО ПЕРЕВІРЯЄ (два інциденти, не більше):
  1. Штамп у блоці зрізу == sha256 секції «Робочий стандарт щозапиту» з CLAUDE.md.
     Змінили секцію, а зріз не переглянули → exit 1.
  2. У блоці для вставки немає назв моделей (закон не-старіння, melania Core Rule 11).

ЧОГО НЕ ЛОВИТЬ (чесно): чи блок ЗМІСТОВНО відповідає секції. Штамп доводить лише
«секцію змінено → хтось відкрив зріз і підставив новий штамп». Це страховка від
забудькуватості, не від недбалості.

Обмеження розбору: секція закінчується на першому наступному рядку, що починається з
«## »; рядок «## » усередині fenced-блоку секції обрізав би її (там такого нема).

Використання:
    python3 scripts/check-portable-standard.py            # гейт
    python3 scripts/check-portable-standard.py --stamp    # надрукувати поточний штамп
    python3 scripts/check-portable-standard.py --root DIR # інший корінь (для тестів)
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
SECTION_HEAD = "## Робочий стандарт щозапиту"
MIN_SECTION_LINES = 5          # «порожній зріз» — помилка перевірки, а не чистота
BEGIN, END = "<!-- BEGIN PASTE -->", "<!-- END PASTE -->"
STAMP_RE = re.compile(r"sha256:([0-9a-f]{12})")
# Назви моделей/вендорів у правилах заборонені законом не-старіння: лише класи.
MODEL_RE = re.compile(
    r"\b(opus|sonnet|haiku|fable|gpt[-\s]?\d\S*|gemini|llama|mistral|claude[-\s]?\d\S*)\b",
    re.I,
)


def section_text(claude_md: str) -> str | None:
    lines = claude_md.splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith(SECTION_HEAD)), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    # rstrip рядків: хвостові пробіли прибирає pre-commit — вони не мають ламати штамп.
    return "\n".join(l.rstrip() for l in lines[start:end]).strip()


def stamp_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stamp", action="store_true", help="надрукувати поточний штамп і вийти")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="корінь репо (для тестів)")
    args = ap.parse_args()

    claude_md = args.root / "CLAUDE.md"
    doc = args.root / "docs" / "portable-standard.md"
    if not claude_md.is_file():
        print(f"❌ немає {claude_md} — перевірити неможливо", file=sys.stderr)
        return 2
    sec = section_text(claude_md.read_text(encoding="utf-8"))
    if sec is None or len(sec.splitlines()) < MIN_SECTION_LINES:
        print(f"❌ у CLAUDE.md не знайдено секцію «{SECTION_HEAD}…» (або вона підозріло коротка) — "
              "перевірити неможливо", file=sys.stderr)
        return 2
    expected = stamp_of(sec)
    if args.stamp:
        print(f"sha256:{expected}")
        return 0

    if not doc.is_file():
        print(f"❌ немає {doc} — перевірити неможливо", file=sys.stderr)
        return 2
    m = re.search(re.escape(BEGIN) + r"(.*?)" + re.escape(END), doc.read_text(encoding="utf-8"), re.S)
    if not m or not m.group(1).strip():
        print(f"❌ у {doc.name} немає непорожнього блоку між {BEGIN} і {END} — перевірити неможливо",
              file=sys.stderr)
        return 2
    block = m.group(1)

    problems: list[str] = []
    stamps = STAMP_RE.findall(block)
    if len(stamps) != 1:
        problems.append(f"у блоці має бути рівно один штамп «sha256:<12 hex>», знайдено {len(stamps)}")
    elif stamps[0] != expected:
        problems.append(
            f"штамп у блоці sha256:{stamps[0]} ≠ поточний sha256:{expected}: секцію «{SECTION_HEAD}…» "
            "у CLAUDE.md змінено. Перегляньте блок у docs/portable-standard.md відповідно до змін, "
            "тоді підставте новий штамп (`python3 scripts/check-portable-standard.py --stamp`)")
    models = sorted({x.group(0) for x in MODEL_RE.finditer(block)}, key=str.lower)
    if models:
        problems.append("у блоці для вставки є назви моделей (закон не-старіння: лише класи): "
                        + ", ".join(models))

    if problems:
        print("❌ переносний стандарт не узгоджений:")
        for p in problems:
            print(f"  ✗ {p}")
        return 1
    print(f"✅ переносний стандарт узгоджений з CLAUDE.md (sha256:{expected}); назв моделей у блоці нема")
    return 0


if __name__ == "__main__":
    sys.exit(main())
