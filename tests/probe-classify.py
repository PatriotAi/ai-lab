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

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "security" / "spine"))
from classify import classify  # noqa: E402

WF = ".github/" + "workflows/evil.yml"
ST = ".claude/" + "settings.json"
SEC = "sec" + "rets"
ENV = "." + "env"
GH = "gh " + "api"
REPO = "repos/o/r"
MERGE_TOOL = "merge_pull" + "_request"

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
    # ── F-21: секрет — R4 і при ЧИТАННІ, будь-яким каналом ──────────────────
    # До фіксу Read секрету давав R4, а `cat` того самого файла — R0.
    ("Bash", f"cat {ENV}", "R4"),
    ("Bash", f"grep KEY {ENV}", "R4"),
    ("Bash", f"head -1 ./{ENV}", "R4"),
    ("Bash", f"git show HEAD:{ENV}", "R4"),
    ("Bash", f"wc -l < {ENV}", "R4"),
    ("Bash", f"cp {ENV} /tmp/x", "R4"),
    ("Bash", f"python3 -c \"print(open('{ENV}').read())\"", "R4"),
    ("Read", ENV, "R4"),
    ("Grep", SEC + "/prod.key", "R4"),
    ("Read", ".claude/" + "settings.local.json", "R4"),
    # Згадка — не читання: друк назви й пошук слова в документації.
    ("Bash", f"echo 'не відкривай {ENV}'", "R0"),
    # Гола назва без пробілів: тут «не читання» тримає саме правило друку, а не
    # відсів фраз (мутант «друк вважається читанням» вижив без цього випадку).
    ("Bash", f"echo {ENV}", "R0"),
    ("Bash", f"grep -rn '{ENV}' docs/", "R0"),
    ("Bash", f"git commit -m 'прибрав {ENV} з індексу'", "R2"),
    # ── W-18 (а): читання налаштувань і воркфлоу — не R4 ────────────────────
    ("Read", WF, "R0"),
    ("Read", ST, "R0"),
    ("Read", "security/" + "policy.toml", "R0"),
    # ── W-18 (б): конвеєр читальних команд із назвою дії в тексті ───────────
    ("Bash", f"grep -rn {MERGE_TOOL} docs | head -5", "R0"),
    # ── F-20: `gh api` на запис — R4; читання лишається R2 ───────────────────
    ("Bash", f"{GH} -X PUT {REPO}/pulls/86/merge", "R4"),
    ("Bash", f"{GH} --method=PATCH {REPO} -f private=false", "R4"),
    ("Bash", f"{GH} -X DELETE {REPO}/git/refs/heads/x", "R4"),
    ("Bash", f"{GH} {REPO}/issues -f title=x", "R4"),
    ("Bash", GH + " graphql -f query='mutation { x }'", "R4"),
    ("Bash", f"bash -c \"{GH} -X PUT {REPO}/pulls/86/merge\"", "R4"),
    ("Bash", f"{GH} {REPO}/pulls/86", "R2"),
    ("Bash", f"{GH} -X GET {REPO}/pulls -f state=open", "R2"),
    ("Bash", GH + " graphql -f query='query { viewer { login } }'", "R2"),
    ("Bash", f"echo '{GH} -X PUT {REPO}/pulls/86/merge'", "R0"),
    # ── Абсолютний шлях — та сама ціль (2026-10-17) ─────────────────────────
    # До фіксу ціль запису порівнювалась лише як написано: Write того самого
    # файла — R4, а запис оболонкою за абсолютним шляхом — R2.
    ("Bash", f"echo x > {ROOT}/{ST}", "R4"),
    ("Bash", f"cp /tmp/x {ROOT}/{WF}", "R4"),
    ("Bash", f"cat {ROOT}/{ENV}", "R4"),
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
