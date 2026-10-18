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
PUSHF = "git " + "push --for" + "ce origin main"    # незворотна дія для «текст як код»
PYW = f"open('{WF}','w').write('x')"                # запис у захищене з інлайн-коду
DEL = "--" + "delete"

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
    # ── Рев'ю #91 (2026-10-18): обходи, кожен відтворено на `d6fa46e` ───────
    # 1. Фоновий `&` — теж роздільник: друга команда виконається.
    ("Bash", "cat README.md & git push --force origin main", "R4"),
    ("Bash", "ls & rm -rf build", "R4"),
    # Виняток (`--force-with-lease`) діє лише у своїй команді ланцюжка.
    ("Bash", "git push --force-with-lease origin br; git push --force origin main", "R4"),
    # 2. Підстановку в подвійних лапках оболонка ВИКОНУЄ; в одинарних — ні.
    ("Bash", 'ls "$(git push --force origin main)"', "R4"),
    ("Bash", f'echo "$(cat {ENV})"', "R4"),
    ("Bash", f'echo "$({GH} -X PUT {REPO}/pulls/86/merge)"', "R4"),
    ("Bash", f"echo `cat {ENV}`", "R4"),
    ("Bash", "echo '$(rm -rf build)'", "R0"),
    # 4. `gh` у лапках, з екрануванням, за повним шляхом — той самий клієнт.
    ("Bash", f"'gh' api -X PUT {REPO}/pulls/86/merge", "R4"),
    ("Bash", f"\\gh api -X PUT {REPO}/pulls/86/merge", "R4"),
    ("Bash", f"/usr/local/bin/gh api -X PUT {REPO}/pulls/86/merge", "R4"),
    ("Bash", f"echo gh api -X PUT {REPO}/pulls/86/merge", "R0"),
    # 5. Об'єднані короткі прапорці: `-iX PUT` — це метод PUT.
    ("Bash", f"{GH} -iX PUT {REPO}/pulls/86/merge", "R4"),
    ("Bash", f"{GH} -iXPUT {REPO}/pulls/86/merge", "R4"),
    # 6. Тіло heredoc, подане в оболонку, — код.
    ("Bash", f"bash <<'EOF'\n{GH} -X PUT {REPO}/pulls/86/merge\nEOF", "R4"),
    # 7. GraphQL-запит, текст якого не видно, — закрито за замовчуванням…
    ("Bash", "Q='mutation{x}'; " + GH + ' graphql -f query="$Q"', "R4"),
    ("Bash", GH + " graphql -f query=$(cat m.graphql)", "R4"),
    # …а змінні GraphQL в одинарних лапках — не підстановка оболонки.
    ("Bash", GH + " graphql -f query='query($o: String!) { repository(owner: $o) { id } }'", "R2"),
    # 8. Відносний шлях після `cd` і через `..` — та сама ціль.
    ("Bash", "cd .claude && echo '{}' > settings.json", "R4"),
    ("Bash", "cd .github && echo x > workflows/ci.yml", "R4"),
    ("Bash", f"cat ../{ROOT.name}/{ENV}", "R4"),
    ("Bash", f"cd docs && cat ../{ENV}", "R4"),
    # 9. Ключі SSH — секрети, і в оболонці теж.
    ("Bash", "cat ~/.ssh/id_ed25519", "R4"),
    ("Bash", "cat /root/.ssh/id_ed25519", "R4"),
    # 10. Абсолютний шлях у вбудованому коді.
    ("Bash", f"python3 -c \"open('{ROOT}/{ST}','w').write('{{}}')\"", "R4"),
    # 11. `#` посеред слова — не коментар; на початку слова — коментар.
    ("Bash", f"cat x# {ENV}", "R4"),
    ("Bash", f"ls # не відкривай {ENV}", "R0"),
    # 12. Прикріплені візерунки й файли: `--regexp=`, `-eX`, `-fФАЙЛ`, `поле=@файл`.
    ("Bash", f"grep --regexp=KEY {ENV}", "R4"),
    ("Bash", f"grep -eKEY {ENV}", "R4"),
    ("Bash", f"grep -fpats.txt {ENV}", "R4"),
    ("Bash", f"sed -ep {ENV}", "R4"),
    ("Bash", f"{GH} -X GET search/code -F q=@{ENV}", "R4"),
    # 13. Фільтр файлів, що прямо називає секрет.
    ("Bash", f"rg -g {ENV} KEY", "R4"),
    ("Bash", f"grep -r --include={ENV} KEY .", "R4"),
    # Here-string подає РЯДОК, а не файл: не читання.
    ("Bash", f"grep KEY <<< {ENV}", "R0"),
    # ── 2026-10-18: полювання на ФОРМИ дії (F-25…F-28) ───────────────────────
    # Кожен випадок, що має ЛОВИТИСЬ, падав на `1be990d`, якщо не позначено
    # інакше (виміряно окремим процесом зі старим кодом: 34 з 46 падають).
    # Випадки з очікуваним R0/R2 — сторожі від хибних тривог НОВОГО розбору:
    # вони проходили й раніше і мають проходити далі.
    # F-27. Оболонка виконує текст — і з кластером прапорців (`-lc`, `-euo … -c`).
    ("Bash", f'bash -lc "{PUSHF}"', "R4"),
    ("Bash", f'bash -ec "{PUSHF}"', "R4"),
    ("Bash", f'bash -euo pipefail -c "{PUSHF}"', "R4"),
    ("Bash", f'sh -xc "{PUSHF}"', "R4"),
    # Номер дескриптора перед перенаправленням — не операнд-скрипт.
    ("Bash", f"bash 2>/dev/null <<'EOF'\n{PUSHF}\nEOF", "R4"),
    # F-27. Інтерпретатор бере програму зі stdin, з /dev/stdin, з конвеєра.
    ("Bash", f"python3 <<'PY'\n{PYW}\nPY", "R4"),
    ("Bash", f"python3 /dev/stdin <<'PY'\n{PYW}\nPY", "R4"),
    ("Bash", f'echo "{PYW}" | python3', "R4"),
    ("Bash", f'python3.12 -c "{PYW}"', "R4"),
    # `-lne`: `-l` бере лише цифри, тож далі `-n` і `-e` (не «аргумент ne»).
    ("Bash", f"perl -lne 'system(\"{PUSHF}\")'", "R4"),
    ("Bash", f"source /dev/stdin <<'EOF'\n{PUSHF}\nEOF", "R4"),
    # F-27. Інші виконавці тексту.
    ("Bash", f"awk 'BEGIN{{system(\"{PUSHF}\")}}'", "R4"),
    ("Bash", f"env -S '{PUSHF}'", "R4"),
    ("Bash", f'su -c "{PUSHF}" root', "R4"),
    ("Bash", f'script -qc "{PUSHF}" /dev/null', "R4"),
    ("Bash", f'flock /tmp/l -c "{PUSHF}"', "R4"),
    ("Bash", f'watch -n1 "{PUSHF}"', "R4"),
    # Ловилось і на `1be990d` — але ВИПАДКОВО, через зайвий збіг «python3 -».
    ("Bash", f'python3 -I -c "{PYW}"', "R4"),
    ("Bash", f'python3 -Bc "{PYW}"', "R4"),
    ("Bash", f'python -W ignore -c "{PYW}"', "R4"),
    # F-27 навпаки: аргумент СКРИПТА в лапках — дані (на `1be990d` було R4).
    ("Bash", f'python3 -I tool.py "{PUSHF}"', "R2"),
    ("Bash", f'python3 -m json.tool "{PUSHF}"', "R2"),
    ("Bash", f'python3 -u tool.py "{PUSHF}"', "R2"),
    # Назва виконавця як аргумент читання — дані.
    ("Bash", "which python3", "R0"),
    ("Bash", "ls /bin/sh", "R0"),
    # F-28. Решта рядка відкривача heredoc — не тіло: ` | bash` і `> файл` лишаються.
    ("Bash", f"cat <<'EOF' | bash\n{PUSHF}\nEOF", "R4"),
    ("Bash", "cat <<'EOF' > notes.md\nтекст\nEOF", "R2"),
    # F-25. Читальний префікс із прапорцем ЗАПИСУ — R2 (журналюється), не R0.
    ("Bash", "git branch -D feature", "R2"),
    ("Bash", "git branch -dr origin/feature", "R2"),
    ("Bash", "git branch -f dev HEAD~3", "R2"),
    ("Bash", "git branch -m old new", "R2"),
    ("Bash", "git diff --output=docs/x.md", "R2"),
    # Ловилось і раніше — випадково: `--delete` містить маркер `find` «-delete».
    ("Bash", f"git branch {DEL} feature", "R2"),
    ("Bash", "git branch -vv", "R0"),
    ("Bash", "git diff -M HEAD~1", "R0"),
    ("Bash", "git branch new-feature", "R0"),       # межа: створення гілки даних не губить
    # F-26. Видалення гілки на сервері — R4 за розбором `git push`.
    ("Bash", f"git push origin {DEL} claude/foo", "R4"),
    ("Bash", "git push -d origin claude/foo", "R4"),
    ("Bash", "git push origin :claude/foo", "R4"),
    ("Bash", f"git push upstream {DEL} x", "R4"),
    ("Bash", "git push --prune origin", "R4"),
    ("Bash", f"git -C /tmp/r push origin {DEL} x", "R4"),
    ("Bash", f'bash -lc "git push origin {DEL} x"', "R4"),
    ("Bash", "git push origin :", "R2"),              # «push matching», не видалення
    ("Bash", f"git push --dry-run origin {DEL} x", "R2"),
    ("Bash", f'echo "git push origin {DEL} x"', "R0"),
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
