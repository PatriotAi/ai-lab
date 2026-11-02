#!/usr/bin/env bash
# run.sh — уся механіка робочого прогону монітора одним викликом (економія ходів моделі).
# Єдина відповідальність: клон відсутніх репо → скан → CI/PR → оновлена сторінка + дельта.
# Нічого не змінює в репозиторіях і не публікує: публікацію робить сесія інструментом Artifact.
#
#   run.sh OUT PAGE OWNER REPO [REPO ...]
#     OUT   — тека для результатів (now.json, ci.json, repo-monitor.html, delta.md)
#     PAGE  — збережена копія сторінки (Artifact read з path "index.html"); не читається → шаблон
#   MON_DIR — куди клонувати (типово ~/mon); MON_NO_CLONE=1 — не клонувати (тести)
# Код виходу: 0 — сторінку зібрано (дельта на stdout); 2 — помилка аргументів або кроку.
set -uo pipefail

[[ $# -ge 4 ]] || { echo "помилка: run.sh OUT PAGE OWNER REPO..." >&2; exit 2; }
OUT="$1"; PAGE="$2"; OWNER="$3"; shift 3
T="$(cd "$(dirname "$0")/../.." && pwd)"
MON="${MON_DIR:-$HOME/mon}"
mkdir -p "$OUT" "$MON" || exit 2
: > "$OUT/clone-errors.txt"

name_ok() { [[ "$1" =~ ^[A-Za-z0-9._-]{1,100}$ ]]; }
name_ok "$OWNER" || { echo "помилка: некоректний owner" >&2; exit 2; }
for r in "$@"; do
  name_ok "$r" || { echo "пропущено некоректну назву репо" >> "$OUT/clone-errors.txt"; continue; }
  [[ -d "$MON/$r/.git" || "${MON_NO_CLONE:-0}" == 1 ]] && continue
  git clone -q --depth 50 "https://github.com/$OWNER/$r.git" "$MON/$r" 2>> "$OUT/clone-errors.txt" \
    || echo "не клонувався: $r" >> "$OUT/clone-errors.txt"
done

python3 -I "$T/scripts/repo-health.py" --root "$MON" --canon "$MON/ai-lab" \
  --waivers "$T/automations/repo-monitor/waivers.json" --json "$OUT/now.json" > "$OUT/full.md" \
  || { echo "помилка: скан (repo-health.py)" >&2; exit 2; }
python3 -I "$T/automations/repo-monitor/ci-state.py" --owner "$OWNER" --from "$OUT/now.json" \
  --json "$OUT/ci.json" > "$OUT/ci.txt" 2>&1 || echo "увага: ci-state завершився з помилкою — CI-стан неповний" >&2

note=""
if ! python3 -I "$T/automations/repo-monitor/update-page.py" --page "$PAGE" --health "$OUT/now.json" \
     --ci "$OUT/ci.json" --out "$OUT/repo-monitor.html" --md "$OUT/delta.md" > /dev/null 2> "$OUT/update.err"; then
  note="⚠️ Сторінку не прочитано ($(head -c 200 "$OUT/update.err")) — дельта від нуля за шаблоном."
  python3 -I "$T/automations/repo-monitor/update-page.py" --page "$T/automations/repo-monitor/page.html" \
    --health "$OUT/now.json" --ci "$OUT/ci.json" --out "$OUT/repo-monitor.html" --md "$OUT/delta.md" > /dev/null \
    || { echo "помилка: update-page" >&2; exit 2; }
fi

cat "$OUT/delta.md"
[[ -n "$note" ]] && echo "$note"
[[ -s "$OUT/clone-errors.txt" ]] && { echo "- Клонування:"; grep -v '^$' "$OUT/clone-errors.txt" | head -20 | sed 's/^/  /'; }
echo "- CI: $(tail -n 1 "$OUT/ci.txt" 2>/dev/null)"
echo "- Сторінка до публікації: $OUT/repo-monitor.html"
exit 0
