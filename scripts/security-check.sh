#!/usr/bin/env bash
# Локальні перевірки безпеки / Local security checks.
#
# Єдина відповідальність: прогнати доступні локальні перевірки й ЧЕСНО звітувати,
# що саме було зроблено.
#
# ТРИ СТАНИ, не два (це і є суть скрипта):
#   ПРОЙДЕНО    — перевірку виконано, вона чиста
#   ВПАЛО       — перевірку виконано, вона знайшла проблему
#   НЕ ГАНЯВСЯ  — інструмента немає, перевірку НЕ виконано
#
# «НЕ ГАНЯВСЯ» ніколи не зараховується як «ПРОЙДЕНО». Раніше зараховувалось:
# за відсутності gitleaks і trivy скрипт друкував «✓ Усі перевірки чисті» і
# виходив із кодом 0, фактично проганяючи одну перевірку з трьох (дефект F-2,
# docs/security/findings-2026-07-27.md). Зелений вердикт, який нічого не
# перевірив, гірший за червоний — він дає хибну впевненість.
#
# Код виходу: 0 — усе, що ганялось, чисте І нічого не пропущено
#             1 — є падіння
#             3 — падінь немає, але частина перевірок НЕ ганялась (неповне покриття)
# Перевизначення: SECURITY_CHECK_ALLOW_SKIPS=1 → пропуски не змінюють код виходу
# (для середовищ, де частина інструментів свідомо не встановлюється).

set -uo pipefail

passed=0
failed=0
skipped=0
declare -a failed_names=()
declare -a skipped_names=()

# run_check <людська назва> <бінарник для перевірки наявності> <команда прогону...>
run_check() {
  local name="$1" probe="$2"
  shift 2
  echo "== $name =="
  if ! command -v "$probe" >/dev/null 2>&1; then
    echo "  ⊘ НЕ ГАНЯВСЯ — інструмент '$probe' не встановлено / not installed"
    skipped=$((skipped + 1))
    skipped_names+=("$name (немає $probe)")
    return
  fi
  if "$@"; then
    echo "  ✓ ПРОЙДЕНО"
    passed=$((passed + 1))
  else
    echo "  ✗ ВПАЛО"
    failed=$((failed + 1))
    failed_names+=("$name")
  fi
}

run_check "pre-commit (гігієна + секрети / hygiene + secrets)" \
  pre-commit pre-commit run --all-files

run_check "gitleaks (секрети в історії / secrets in history)" \
  gitleaks gitleaks detect --no-banner

run_check "trivy (вразливості й misconfig / vulns and misconfig)" \
  trivy trivy fs --config security/trivy.yaml .

echo ""
echo "════════ ПІДСУМОК / SUMMARY ════════"
printf "  ПРОЙДЕНО: %d · ВПАЛО: %d · НЕ ГАНЯВСЯ: %d\n" "$passed" "$failed" "$skipped"

if (( failed > 0 )); then
  printf "  ✗ Впали / failed:\n"
  printf "     - %s\n" "${failed_names[@]}"
fi
if (( skipped > 0 )); then
  printf "  ⊘ Не ганялись / not run:\n"
  printf "     - %s\n" "${skipped_names[@]}"
fi

if (( failed > 0 )); then
  echo "  ВЕРДИКТ: є падіння — виправ їх / failures present."
  exit 1
fi

if (( skipped > 0 )); then
  if [[ "${SECURITY_CHECK_ALLOW_SKIPS:-0}" == "1" ]]; then
    echo "  ВЕРДИКТ: те, що ганялось, чисте; пропуски дозволено явно (SECURITY_CHECK_ALLOW_SKIPS=1)."
    exit 0
  fi
  echo "  ВЕРДИКТ: НЕПОВНЕ ПОКРИТТЯ — те, що ганялось, чисте, але $skipped перевірок не виконано."
  echo "           Це НЕ означає «безпечно» / this does NOT mean 'secure'."
  echo "           Встанови інструменти: bash scripts/setup.sh"
  echo "           Або дозволь пропуски явно: SECURITY_CHECK_ALLOW_SKIPS=1"
  exit 3
fi

echo "  ВЕРДИКТ: усі перевірки виконано, усі чисті / all checks ran and are clean"
exit 0
