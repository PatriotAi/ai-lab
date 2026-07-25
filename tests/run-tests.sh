#!/usr/bin/env bash
# run-tests.sh — регресійні тести автоматизацій лабораторії.
# Єдина відповідальність: довести ділом, що критична інфраструктура (stop-хук
# git-перевірки, G5-цикл памʼяті, щотижневий дайджест, SessionStart-контекст)
# працює як описано. Без мережі, без секретів, без залежностей понад git+python3.
#
# Запуск локально:  bash tests/run-tests.sh
# У CI:             .github/workflows/code-quality.yml → job "automations tests"
# Код виходу: 0 — усі тести пройшли; 1 — є падіння (список у підсумку).
set -uo pipefail

REPO="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
HOOK="$REPO/automations/stop-git-check/stop-hook-git-check.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT

PASS=0; FAIL=0; FAILED=()

ok()   { PASS=$((PASS+1)); printf '  ✅ %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); FAILED+=("$1"); printf '  ❌ %s\n     очікували: %s\n     отримали:  %s\n' "$1" "$2" "$3"; }
check(){ # check <назва> <очікуване> <фактичне>
  [[ "$2" == "$3" ]] && ok "$1" || bad "$1" "$2" "$3"; }

# Тимчасовий git-репозиторій із фейковим remote (хук виходить тихо без remote).
# ВАЖЛИВО: викликати БЕЗ підоболонки — `mk_repo name`, не `d=$(mk_repo name)`.
# Інакше `cd` не подіє на батьківський шел і git-команди тесту підуть у РОБОЧИЙ
# репозиторій (реальний баг, спійманий 2026-07-21: тести наробили сміттєвих
# комітів у гілці). Після виклику поточна тека = тека тесту ($PWD).
mk_repo() {
  local d="$TMPROOT/$1"; mkdir -p "$d"
  cd "$d" || { echo "mk_repo: cd не вдався: $d" >&2; exit 1; }
  git init -q -b main .
  git config user.email t@example.com; git config user.name Tester
  git config commit.gpgsign false
  echo seed > seed.txt; git add seed.txt
  git commit -q --no-gpg-sign -m "seed"
  git remote add origin "$d"          # self-remote: origin/* резолвиться локально
  git update-ref refs/remotes/origin/main HEAD
  git update-ref refs/remotes/origin/HEAD HEAD
  # Запобіжник: якщо ми раптом опинились у робочому репо — негайно спинитись
  [[ "$(git rev-parse --show-toplevel)" == "$d" ]] || {
    echo "mk_repo: ІЗОЛЯЦІЯ ПОРУШЕНА (працюємо не в tmp!) — зупинка" >&2; exit 1; }
}

echo "════════ 1. Stop-хук: класифікатор комітів (R1–R5) ════════"

# 1.1 Справді непідписаний сторонній коміт → FIX (exit 2)
mk_repo unsigned
echo x > a.txt; git add a.txt
git -c user.email=stranger@example.com -c user.name=S commit -q --no-gpg-sign -m "чужий непідписаний"
out=$(STOP_HOOK_TEST_RANGE="origin/main..HEAD" bash "$HOOK" < /dev/null 2>&1); rc=$?
check "непідписаний сторонній → exit 2" "2" "$rc"
[[ "$out" == *FIX* && "$out" == *R5* ]] && ok "звіт містить вердикт FIX/R5" \
  || bad "звіт містить вердикт FIX/R5" "FIX+R5 у виводі" "${out:0:80}"

# 1.2 Анти-маскування: слово gpgsig у ТІЛІ повідомлення не робить коміт «підписаним»
mk_repo spoof
echo y > b.txt; git add b.txt
git -c user.email=noreply@anthropic.com -c user.name=Claude commit -q --no-gpg-sign \
  -m "спроба маскування" -m "gpgsig підроблений-рядок-у-тілі"
rc=$(STOP_HOOK_TEST_RANGE="origin/main..HEAD" bash "$HOOK" < /dev/null >/dev/null 2>&1; echo $?)
check "spoof «gpgsig» у повідомленні → все одно exit 2" "2" "$rc"

# 1.3 Юніт статусів підпису: прийнятні G/U/E, неприйнятні N/B/X/Y/R
sig_src=$(sed -n '/^sig_ok()/,/^}/p' "$HOOK")
for s in G U E; do
  rc=$(bash -c "$sig_src; sig_ok $s" >/dev/null 2>&1; echo $?)
  check "статус підпису $s — прийнятний" "0" "$rc"
done
for s in N B X Y R; do
  rc=$(bash -c "$sig_src; sig_ok $s" >/dev/null 2>&1; echo $?)
  check "статус підпису $s — НЕприйнятний" "1" "$rc"
done

# 1.4 Штатні перевірки чистоти дерева збережено
mk_repo dirty; echo z >> seed.txt
rc=$(bash "$HOOK" <<<'{}' >/dev/null 2>&1; echo $?)
check "незакомічені зміни → exit 2" "2" "$rc"

mk_repo untracked; echo new > untracked.txt
rc=$(bash "$HOOK" <<<'{}' >/dev/null 2>&1; echo $?)
check "незатрековані файли → exit 2" "2" "$rc"

# 1.5 Захист від рекурсії: stop_hook_active=true → мовчазний вихід 0
mk_repo recursion; echo dirty >> seed.txt
rc=$(bash "$HOOK" <<<'{"stop_hook_active":true}' >/dev/null 2>&1; echo $?)
check "stop_hook_active=true → exit 0 (без рекурсії)" "0" "$rc"

echo ""
echo "════════ 2. G5: витяг памʼяті (g5-retrieve) ════════"
cd "$REPO" || exit 1
FIX="$TMPROOT/pkg"; mkdir -p "$FIX"
cat > "$FIX/g5-package.md" <<'EOF'
# TEST PACKAGE
## 0. KEY — глосарій
- термін-маркер-KEY
## 1. STATE
- стан-маркер-STATE
## 2. DECISIONS
- рішення-маркер-DEC
## 3. OPEN THREADS
- нитка-маркер-THREAD
## 4. EXACT NEXT STEP
- крок-маркер-NEXT
## 5. ШУМ (не має потрапити)
- шум-маркер-NOISE
EOF
out=$(python3 "$REPO/scripts/g5-retrieve.py" "$FIX/g5-package.md" 2>&1)
for m in KEY STATE DEC THREAD NEXT; do
  [[ "$out" == *"маркер-$m"* ]] && ok "витягнуто секцію $m" \
    || bad "витягнуто секцію $m" "маркер-$m у виводі" "відсутній"
done
[[ "$out" != *"маркер-NOISE"* ]] && ok "зайву секцію (ШУМ) НЕ витягнуто" \
  || bad "зайву секцію НЕ витягнуто" "без маркер-NOISE" "шум просочився"

# Відсутній пакет → не падає жорстко, повідомляє
rc=$(python3 "$REPO/scripts/g5-retrieve.py" "$TMPROOT/nope" >/dev/null 2>&1; echo $?)
[[ "$rc" -le 1 ]] && ok "відсутній пакет → керована помилка (rc≤1)" \
  || bad "відсутній пакет → керована помилка" "rc≤1" "rc=$rc"

echo ""
echo "════════ 3. G5: консолідація (g5-consolidate) ════════"
# Реальний контекст використання: тека ВСЕРЕДИНІ git-репозиторію (як у Stop-хуку)
mk_repo consol; CD="$PWD"; mkdir -p "$CD/subdir"; echo file > "$CD/subdir/f.md"

python3 "$REPO/scripts/g5-consolidate.py" subdir >/dev/null 2>&1
[[ -f "$CD/subdir/AUTO-STATE.md" ]] && ok "AUTO-STATE.md створено (тека в git-репо)" \
  || bad "AUTO-STATE.md створено (тека в git-репо)" "файл існує" "файлу немає"
if [[ -f "$CD/subdir/AUTO-STATE.md" ]]; then
  grep -q 'AUTO-STATE' "$CD/subdir/AUTO-STATE.md" && ok "вміст має заголовок AUTO-STATE" \
    || bad "вміст має заголовок AUTO-STATE" "заголовок" "відсутній"
  h1=$(grep -v '^- \*\*Час:' "$CD/subdir/AUTO-STATE.md" | sha256sum | cut -d' ' -f1)
  python3 "$REPO/scripts/g5-consolidate.py" subdir >/dev/null 2>&1
  h2=$(grep -v '^- \*\*Час:' "$CD/subdir/AUTO-STATE.md" | sha256sum | cut -d' ' -f1)
  check "детермінований (двічі — той самий вміст, окрім мітки часу)" "$h1" "$h2"
fi
cd "$REPO" || exit 1
rc=$(python3 "$REPO/scripts/g5-consolidate.py" "$TMPROOT/не-тека" >/dev/null 2>&1; echo $?)
[[ "$rc" -le 1 ]] && ok "неіснуюча тека → керована помилка" \
  || bad "неіснуюча тека → керована помилка" "rc≤1" "rc=$rc"
# Регрес (знайдено тестами 2026-07-21): тека поза git → зрозуміле повідомлення, НЕ трейсбек
err=$(python3 "$REPO/scripts/g5-consolidate.py" "$TMPROOT" 2>&1 >/dev/null)
[[ "$err" != *Traceback* ]] && ok "тека поза git → керована відмова без трейсбека" \
  || bad "тека поза git → керована відмова без трейсбека" "повідомлення" "сирий Traceback"

echo ""
echo "════════ 4. Щотижневий дайджест ════════"
cd "$REPO" || exit 1
dg=$(bash scripts/weekly-digest.sh 2>&1); rc=$?
check "weekly-digest завершується успішно" "0" "$rc"
for sec in "Щотижневий дайджест" "Активність за 7 днів" "Статус плану" "Наступний крок"; do
  [[ "$dg" == *"$sec"* ]] && ok "секція «$sec» присутня" \
    || bad "секція «$sec» присутня" "$sec" "відсутня"
done
[[ "$dg" =~ Комітів:\ \*\*[0-9]+\*\* ]] && ok "лічильник комітів — число" \
  || bad "лічильник комітів — число" "Комітів: **N**" "не знайдено"

echo ""
echo "════════ 5. SessionStart: контекст сесії ════════"
ss=$(bash automations/session-start/session-start.sh 2>&1); rc=$?
check "session-start завершується успішно" "0" "$rc"
python3 -c "
import json,sys
d=json.loads(sys.stdin.read())
assert d['hookSpecificOutput']['hookEventName']=='SessionStart'
assert len(d['hookSpecificOutput']['additionalContext'])>50
" <<<"$ss" 2>/dev/null && ok "віддає валідний JSON hookSpecificOutput" \
  || bad "віддає валідний JSON hookSpecificOutput" "валідний JSON" "невалідний/порожній"

echo ""
echo "════════ 6. Проєкт: кишеньковий агент (projects/mobile-agent) ════════"
cd "$REPO" || exit 1
if command -v node >/dev/null 2>&1; then
  ma_out=$(node tests/mobile-agent-tests.mjs 2>&1); ma_rc=$?
  # Вивід підпорядкованого набору показуємо як є (він у тому ж форматі ✅/❌),
  # а його лічильники додаємо до загальних, щоб підсумок був чесний.
  sed -e '/^TOTALS /d' -e '/^Впали:/,$d' <<<"$ma_out"
  ma_totals=$(grep -o 'TOTALS pass=[0-9]* fail=[0-9]*' <<<"$ma_out" | tail -1)
  ma_pass=$(sed -n 's/.*pass=\([0-9]*\).*/\1/p' <<<"$ma_totals")
  ma_fail=$(sed -n 's/.*fail=\([0-9]*\).*/\1/p' <<<"$ma_totals")
  if [[ -z "$ma_totals" ]]; then
    bad "набір тестів проєкту завершився коректно" "рядок TOTALS" "rc=$ma_rc, без підсумку"
  else
    PASS=$((PASS + ma_pass)); FAIL=$((FAIL + ma_fail))
    while IFS= read -r line; do FAILED+=("${line#  - }"); done < <(sed -n '/^Впали:/,$p' <<<"$ma_out" | tail -n +2)
  fi
else
  echo "  ⏭  node недоступний — тести проєкту пропущено (не падіння)"
fi

echo ""
echo "════════ ПІДСУМОК ════════"
printf "  пройдено: %d · впало: %d\n" "$PASS" "$FAIL"
if (( FAIL > 0 )); then
  printf "  ❌ Впали:\n"; printf "     - %s\n" "${FAILED[@]}"
  exit 1
fi
printf "  ✅ Усі тести автоматизацій пройдено\n"
