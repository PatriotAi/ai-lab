#!/usr/bin/env python3
"""check-conflict-markers.py — незакриті маркери конфлікту у відстежуваних файлах.

НАВІЩО ОКРЕМА ПЕРЕВІРКА, ЯКЩО Є pre-commit. Хук `check-merge-conflict` ганяється
на комітах ГІЛКИ. **Merge-коміт його оминає**: гілка чиста, PR зелений, а розв'язання
конфлікту зроблене в UI потрапляє в `main` як є. Саме так у канонічний журнал
`docs/learnings.md` потрапили `<<<<<<< HEAD` / `>>>>>>> origin/main` і прожили там
до 2026-09-28 — жодна з 236 перевірок їх не бачила.

Запуск: python3 scripts/check-conflict-markers.py [корінь]
Код виходу: 0 — чисто · 1 — знайдено маркери · 2 — помилка виклику.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

# Рядок-маркер саме на початку рядка: так у тексті можна спокійно ЗГАДУВАТИ
# маркери (як робить цей файл і tests/README), не ламаючи перевірку.
MARKERS = re.compile(r"^(<{7} |={7}$|>{7} )", re.M)
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".skill"}


def tracked_files(root: pathlib.Path) -> list[pathlib.Path]:
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files"],
                             capture_output=True, text=True, check=True).stdout
        return [root / line for line in out.splitlines() if line]
    except Exception:
        return [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[1] if len(argv) > 1 else ".").resolve()
    if not root.is_dir():
        print(f"check-conflict-markers: не тека: {root}", file=sys.stderr)
        return 2
    hits = []
    for f in tracked_files(root):
        if f.suffix.lower() in SKIP_SUFFIX or not f.is_file():
            continue
        if f.resolve() == pathlib.Path(__file__).resolve():
            continue  # цей файл описує маркери в докстрінгу
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if MARKERS.match(line):
                hits.append(f"{f.relative_to(root)}:{i}: {line[:40]}")
    if hits:
        print(f"🛑 незакриті маркери конфлікту — {len(hits)}:")
        for h in hits:
            print(f"  ✗ {h}")
        print("  Це залишок незавершеного злиття: файл містить ОБИДВІ версії одночасно.")
        return 1
    print("✅ незакритих маркерів конфлікту немає")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
