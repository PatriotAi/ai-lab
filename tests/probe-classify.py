#!/usr/bin/env python3
"""probe-classify.py — стенд для класифікатора дій.

Навіщо окремий файл, а не однорядковик у shell: перевіряти гейт командою, що
сама містить захищені шляхи й слова на кшталт `secrets`, — означає перевіряти
власний текст, а не поведінку. Тут рядки будуються зі шматків, тож стенд не
тригерить те, що вимірює.

Запуск: python3 tests/probe-classify.py   (0 — усі збіги, 1 — є розбіжності)
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "security" / "spine"))
from classify import classify  # noqa: E402

WF = ".github/" + "workflows/evil.yml"
ST = ".claude/" + "settings.json"
SEC = "sec" + "rets"

CASES: list[tuple[str, str, str]] = [
    # Запис у захищене — має ловитись, навіть через оболонку.
    ("Bash", f"cat > {WF}", "R4"),
    ("Bash", f"echo x >> {ST}", "R4"),
    ("Bash", "tee .env", "R4"),
    ("Bash", f"python3 gen.py > {WF}", "R4"),
    ("Bash", f"cp /tmp/x {ST}", "R4"),
    # Згадка без запису — НЕ має ловитись (інакше гейт кричить на порожньому).
    # R2, а не R0: ланцюжок через `;` не є чистим читанням. Головне — НЕ R4:
    # слово в тексті не має вмикати правило про ключі.
    ("Bash", f"echo 'перевіряю {SEC} у звіті'; ls", "R2"),
    ("Bash", f"grep -r {SEC} docs/", "R0"),
    ("Bash", f"python3 -c 'import sys; print(\"{WF}\")'", "R2"),
    # Звичайна робота — має лишатись дешевою.
    ("Bash", "cat docs/PLAN.md", "R0"),
    ("Bash", "git status", "R0"),
    ("Bash", "npm test", "R2"),
    ("Bash", "cat a.txt > b.txt", "R2"),
    ("Bash", "git push --force-with-lease origin br", "R2"),
    # Незворотне за командою.
    ("Bash", "git push --force origin main", "R4"),
    ("Bash", "rm -rf build", "R4"),
    # Інструменти.
    ("Read", "docs/PLAN.md", "R0"),
    ("Write", "docs/learnings.md", "R1"),
    ("Write", ST, "R4"),
    ("WebFetch", "https://example.com", "R3"),
]


def main() -> int:
    bad = 0
    for tool, payload, want in CASES:
        tool_input = {"command": payload} if tool == "Bash" else {"file_path": payload}
        got = classify(tool, tool_input).level
        if got != want:
            bad += 1
            print(f"  ❌ {payload[:52]:<54} очік={want} факт={got}")
    total = len(CASES)
    print(f"  класифікатор: {total - bad}/{total} збігів")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
