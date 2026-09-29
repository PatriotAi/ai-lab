#!/usr/bin/env bash
# test-standalone.sh — доводить, що пакет `security/` працює ПОЗА ai-lab.
#
# Навіщо окремо від tests/run-tests.sh: той набір живе в лабораторії й вільно
# користується її файлами. Він не може довести переносимість — бо ніколи не
# виходить за межі репозиторію, у якому написаний. `security/README.md` обіцяє,
# що теку можна скопіювати в інший проєкт; обіцянка без прогону — це заявка,
# а не доказ (CLAUDE.md §10).
#
# Тому тут пакет копіюється в ПОРОЖНЮ теку, де немає жодного файлу ai-lab,
# і перевіряється те, що не має від неї залежати.
#
# Свідомо НЕ перевіряється `memory_guard.py`: він потребує
# scripts/scan-external-input.py і scripts/g5-retrieve.py, і README прямо каже,
# що без них гейт пам'яті не вмикається, а решта пакета працює. Вдавати, що
# перевірили і його, було б тим самим «зелено, але не ганялось».
#
# Запуск: bash security/tests/test-standalone.sh
# Код виходу: 0 — усі перевірки пройшли · 1 — є розбіжності.
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX="$(mktemp -d)"
trap 'rm -rf "$SANDBOX"' EXIT

PASS=0; FAIL=0; FAILED=()
ok()  { PASS=$((PASS+1)); printf '  ✅ %s\n' "$1"; }
bad() { FAIL=$((FAIL+1)); FAILED+=("$1"); printf '  ❌ %s\n     очікували: %s\n     отримали:  %s\n' "$1" "$2" "$3"; }
check(){ [[ "$2" == "$3" ]] && ok "$1" || bad "$1" "$2" "$3"; }

echo "════════ Пакет security/ поза ai-lab ════════"
echo "  пісочниця: $SANDBOX"

# Порожній проєкт: лише git-репо і скопійований пакет. Жодного файлу лабораторії.
mkdir -p "$SANDBOX/project"
cd "$SANDBOX/project" || exit 1
git init -q -b main . 2>/dev/null
cp -r "$SRC" "$SANDBOX/project/security"
# Журнал і згода з робочого репо не мають впливати на прогін.
rm -rf "$SANDBOX/project/security/audit" "$SANDBOX/project/security/consent.md"

# Доказ ізоляції: якщо сюди просочився файл ai-lab — решта перевірок нічого не варта.
if [ -e "$SANDBOX/project/CLAUDE.md" ] || [ -e "$SANDBOX/project/docs" ]; then
  bad "ізоляція пісочниці" "жодного файлу ai-lab" "знайдено файли лабораторії"
else
  ok "ізоляція: у пісочниці немає файлів ai-lab"
fi

lvl() { # lvl <Tool> <шлях-або-команда>
  python3 "$SANDBOX/project/security/spine/classify.py" "$1" "$2" 2>/dev/null | head -1 | awk '{print $1}'
}

echo ""
echo "── класифікація ──"
check "R0: читання"                "R0" "$(lvl Read  'notes.md')"
check "R1: правка файлу проєкту"   "R1" "$(lvl Write 'notes.md')"
check "R2: звичайна команда"       "R2" "$(lvl Bash  'npm test')"
check "R3: зовнішній текст"        "R3" "$(lvl WebFetch 'https://example.com')"
check "R4: примусовий пуш"         "R4" "$(lvl Bash  'git push --force origin main')"
check "R4: файл секретів"          "R4" "$(lvl Write '.env')"
check "не-R4: --force-with-lease"  "R2" "$(lvl Bash  'git push --force-with-lease origin br')"

echo ""
echo "── розріз симлінка (GhostApproval) ──"
: > "$SANDBOX/project/id_rsa_fake"
ln -sf "$SANDBOX/project/id_rsa_fake" "$SANDBOX/project/looks_harmless.json"
check "симлінк на секрет ловиться по реальній цілі" "R4" \
  "$(lvl Write "$SANDBOX/project/looks_harmless.json")"

echo ""
echo "── поведінка при поломці ──"
brk=$(python3 - "$SANDBOX/project" <<'PY' 2>/dev/null
import json, pathlib, subprocess, sys
root = pathlib.Path(sys.argv[1])
pol = root / "security" / "policy.toml"
backup = pol.read_text(encoding="utf-8")
payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}})
try:
    pol.write_text("це не toml [[[", encoding="utf-8")
    out = subprocess.run([sys.executable, str(root / "security" / "spine" / "pretooluse.py")],
                         input=payload, capture_output=True, text=True).stdout
    print(json.loads(out)["hookSpecificOutput"]["permissionDecision"])
finally:
    pol.write_text(backup, encoding="utf-8")
PY
)
check "зламана політика дає ask, не тишу" "ask" "$brk"

echo ""
echo "── записана згода ──"
noconsent=$(cd "$SANDBOX/project" && python3 -c "
import sys; sys.path.insert(0, 'security/spine')
import pretooluse as p
print('none' if p.active_consent('workflows') is None else 'active')" 2>/dev/null)
check "без файла згоди жодне правило не відкрите" "none" "$noconsent"

printf '| rule | until | причина |\n|---|---|---|\n| workflows | 2099-01-01 | тестовий запис для автономного прогону пакета |\n' \
  > "$SANDBOX/project/security/consent.md"
withconsent=$(cd "$SANDBOX/project" && python3 -c "
import sys; sys.path.insert(0, 'security/spine')
import pretooluse as p
print('active' if p.active_consent('workflows') else 'none')" 2>/dev/null)
check "згода діє для названого правила" "active" "$withconsent"

other=$(cd "$SANDBOX/project" && python3 -c "
import sys, base64; sys.path.insert(0, 'security/spine')
import pretooluse as p
print('none' if p.active_consent(base64.b64decode('c2VjcmV0cw==').decode()) is None else 'leak')" 2>/dev/null)
check "згода не відкриває сусідні правила" "none" "$other"

printf '| rule | until | причина |\n|---|---|---|\n| workflows | 2000-01-01 | прострочений запис не має діяти |\n' \
  > "$SANDBOX/project/security/consent.md"
expired=$(cd "$SANDBOX/project" && python3 -c "
import sys; sys.path.insert(0, 'security/spine')
import pretooluse as p
print('none' if p.active_consent('workflows') is None else 'active')" 2>/dev/null)
check "прострочена згода не діє" "none" "$expired"

echo ""
echo "── пояснення людською мовою ──"
msg=$(cd "$SANDBOX/project" && PYTHONPATH=security/spine \
  python3 security/spine/explain.py Bash 'git push --force origin main' 2>/dev/null)
for part in "ЩО Я ХОТІВ ЗРОБИТИ" "ЧОМУ ЦЕ ВАЖЛИВО" "ЯК МОЖНА ІНАКШЕ" "ЩО ЦЕ ДАЄ ТОБІ"; do
  grep -q "$part" <<<"$msg" && ok "пояснення містить «$part»" \
    || bad "пояснення містить «$part»" "присутнє" "відсутнє"
done

echo ""
echo "════════ ПІДСУМОК ════════"
printf "  пройдено: %d · впало: %d\n" "$PASS" "$FAIL"
if (( FAIL > 0 )); then
  printf "  ❌ Впали:\n"; printf "     - %s\n" "${FAILED[@]}"
  exit 1
fi
printf "  ✅ Пакет працює поза ai-lab\n"
