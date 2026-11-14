#!/usr/bin/env python3
"""Канарки гейта scripts/check-portable-standard.py (Core Rule 15: перевірка, що лише
проходить на чистому, не доводить нічого).

Для кожної поломки гейт має ЗАВЕРШИТИСЬ потрібним кодом І з потрібної ПРИЧИНИ
(підрядок у виводі): мутант, спійманий не тим, чим мав, — це канарка, що брешить.
Контролі (чисті стани, зміни поза секцією, кінцеві пробіли) мають ПРОЙТИ мовчки.

Працює у тимчасових теках (TemporaryDirectory), репо не чіпає і не копіює — ~0,3 с.

Протокол виводу для tests/run-tests.sh (рядки з табуляціями):
    OK <назва>                          — сценарій поводиться як очікувано
    BAD <назва> <очікувано> <отримано>  — ні
    DONE <кількість>                    — скрипт дійшов до кінця (без цього рядка прогін
                                          не зараховується: падіння не має виглядати чистотою)
Код виходу: 0 — усе ОК; 1 — є BAD.

Використання:
    python3 tests/portable-standard-canary.py [шлях-до-гейта]   # інший гейт — для самоперевірки канарок
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATE = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "scripts" / "check-portable-standard.py"

# Незалежні літерали (не імпорт із гейта): спільна помилка в константах не мала б
# одночасно ламати і гейт, і його канарки.
HEAD = "## Робочий стандарт щозапиту"
BEGIN, END = "<!-- BEGIN PASTE -->", "<!-- END PASTE -->"
STAMP = re.compile(r"sha256:[0-9a-f]{12}")


def bounds(lines: list[str]) -> tuple[int, int]:
    s = next(i for i, l in enumerate(lines) if l.startswith(HEAD))
    e = next((i for i in range(s + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return s, e


def body(lines: list[str]) -> list[int]:
    """Індекси непорожніх рядків усередині секції (за структурою, не за формулюванням)."""
    s, e = bounds(lines)
    return [i for i in range(s + 1, e) if lines[i].strip()]


def edit_line(n: int, fn):
    def m(t: str) -> str:
        L = t.split("\n")
        i = body(L)[n]
        L[i] = fn(L[i])
        return "\n".join(L)
    return m


def truncate_section(t: str) -> str:
    L = t.split("\n")
    s, e = bounds(L)
    L[s + 1:e] = ["x", ""]
    return "\n".join(L)


def second_stamp(t: str) -> str:
    m = STAMP.search(t)
    return t[:m.end()] + " " + m.group(0) + t[m.end():]


def with_text(text: str):
    return lambda t: t.replace(BEGIN, BEGIN + "\n" + text + "\n", 1)


KEEP = None
# (назва, мутація CLAUDE.md, мутація зрізу | "DROP", очікуваний код, підрядок причини)
SCENARIOS = [
    ("контроль: чистий стан — гейт мовчить", KEEP, KEEP, 0, "узгоджений"),
    ("контроль: кінцеві пробіли в рядку секції не ламають штамп",
     edit_line(1, lambda s: s + "   "), KEEP, 0, "узгоджений"),
    ("контроль: кінцева табуляція в рядку секції не ламає штамп",
     edit_line(2, lambda s: s + "\t"), KEEP, 0, "узгоджений"),
    ("контроль: зміна ПОЗА секцією не ламає штамп (немає хибних тривог)",
     lambda t: t + "\n<!-- поза секцією -->\n", KEEP, 0, "узгоджений"),
    ("пробіли ВСЕРЕДИНІ рядка секції — це зміна вмісту → штамп застарів",
     edit_line(0, lambda s: s.replace(" ", "   ", 1)), KEEP, 1, "≠ поточний"),
    ("секцію змінено, зріз не переглянуто → штамп застарів",
     edit_line(0, lambda s: s + " ЗМІНА"), KEEP, 1, "≠ поточний"),
    ("штамп у зрізі видалено", KEEP, lambda t: STAMP.sub("sha256:", t), 1, "рівно один штамп"),
    ("у зрізі два штампи", KEEP, second_stamp, 1, "рівно один штамп"),
    ("у зрізі назва моделі (Sonnet)", KEEP, with_text("Sonnet"), 1, "назви моделей"),
    ("у зрізі ідентифікатор моделі (claude-opus-4-8)", KEEP, with_text("claude-opus-4-8"), 1, "назви моделей"),
    ("немає маркера блоку вставки → перевірити неможливо (не «ок»)",
     KEEP, lambda t: t.replace(BEGIN, "", 1), 2, "перевірити неможливо"),
    ("секцію в CLAUDE.md перейменовано → перевірити неможливо (не «ок»)",
     lambda t: t.replace(HEAD, "## Інша назва", 1), KEEP, 2, "перевірити неможливо"),
    ("секцію усічено до заглушки → перевірити неможливо (не «ок»)",
     truncate_section, KEEP, 2, "перевірити неможливо"),
    ("файлу зрізу немає → перевірити неможливо (не «ок»)", KEEP, "DROP", 2, "перевірити неможливо"),
]


def run(root: Path) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(GATE), "--root", str(root)], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    claude = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    doc = (REPO / "docs" / "portable-standard.md").read_text(encoding="utf-8")
    bad = 0

    def report(name: str, ok: bool, want, got) -> None:
        nonlocal bad
        if ok:
            print(f"OK\t{name}")
        else:
            bad += 1
            print(f"BAD\t{name}\t{want}\t{str(got).replace(chr(10), ' ')[:200]}")

    for name, m_claude, m_doc, want_rc, want_text in SCENARIOS:
        c, d = claude, doc
        if m_claude:
            c = m_claude(claude)
            if c == claude:
                report(name, False, "мутація CLAUDE.md змінює файл", "мутація нічого не змінила (канарка недійсна)")
                continue
        if m_doc and m_doc != "DROP":
            d = m_doc(doc)
            if d == doc:
                report(name, False, "мутація зрізу змінює файл", "мутація нічого не змінила (канарка недійсна)")
                continue
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs").mkdir()
            (root / "CLAUDE.md").write_text(c, encoding="utf-8")
            if m_doc != "DROP":
                (root / "docs" / "portable-standard.md").write_text(d, encoding="utf-8")
            rc, out = run(root)
        report(name, rc == want_rc and want_text in out, f"exit {want_rc} і «{want_text}»", f"exit {rc}: {out.strip()}")

    # Контроль на РЕАЛЬНОМУ репо: те, що отримає pre-commit/CI.
    rc, out = run(REPO)
    report("реальний репозиторій: зріз узгоджений із CLAUDE.md", rc == 0, "exit 0", f"exit {rc}: {out.strip()}")

    print(f"DONE\t{len(SCENARIOS) + 1}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
